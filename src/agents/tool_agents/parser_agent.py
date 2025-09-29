"""Parser agent responsible for preparing LaTeX inputs for translation."""

from typing import Dict, Any, Optional
from src.agents.tool_agents.base_tool_agent import BaseToolAgent
import src.formats.latex.prompts as pm
from pathlib import Path
import sys
import os
import requests
import time
from tqdm import tqdm

# Optional Ollama support to mirror translator agent behaviour
try:
    import ollama

    OLLAMA_AVAILABLE = True
except ImportError:
    ollama = None  # type: ignore[assignment]
    OLLAMA_AVAILABLE = False

base_dir = os.getcwd()
sys.path.append(base_dir)


class ParserAgent(BaseToolAgent):
    """Parse LaTeX projects and flag environments that require translation."""

    def __init__(self, config: Dict[str, Any], project_dir: str, output_dir: str):
        """Initialize the parser agent with runtime configuration and paths.

        Parameters
        ----------
        config:
            Configuration dictionary including LLM connection details.
        project_dir:
            Absolute path to the LaTeX project that should be parsed.
        output_dir:
            Destination directory where parsed JSON artefacts will be stored.
        """

        super().__init__(agent_name="ParserAgent", config=config)

        self.config = config
        self.project_dir = project_dir  # Project path for parsing
        self.output_dir = output_dir  # Output directory for parsed files
        self.model = config["llm_config"].get("model", "gpt-4o")
        self.base_url = config["llm_config"].get("base_url")
        self.API_KEY = config["llm_config"].get("api_key")

        self.use_ollama = self._is_ollama_endpoint(self.base_url)
        self.ollama_host: Optional[str] = None
        if self.use_ollama:
            if not OLLAMA_AVAILABLE:
                raise ImportError(
                    "Ollama package not installed. Please install with: pip install ollama"
                )
            assert self.base_url is not None
            self.ollama_host = self.base_url.replace("/v1/chat/completions", "")

    @staticmethod
    def _is_ollama_endpoint(base_url: Optional[str]) -> bool:
        """Return ``True`` if the provided endpoint appears to target Ollama."""

        if not base_url:
            return False
        lowered = base_url.lower()
        return "localhost:11434" in lowered or "ollama" in lowered

    def execute(self, data: Any = None, **kwargs: Any) -> Any:
        """Parse the LaTeX project and evaluate translation requirements.

        The method drives the parsing process, identifies environments that
        should be translated, runs the LLM heuristic for ambiguous cases, and
        persists the resulting structured metadata to disk.
        """

        pm.init_prompts(self.config["source_language"], self.config["target_language"])
        self.log(
            f"🤖💬 Starting parsing for project...⏳: {os.path.basename(self.project_dir)}."
        )

        from src.formats.latex.parser import LatexParser

        latex_parser = LatexParser(self.project_dir, self.output_dir)
        latex_parser.parse()

        env_need_trans = []
        if latex_parser.envs_json:
            for env in latex_parser.envs_json:
                if env["need_trans"] and env["env_name"] not in ["abstract", "itemize"]:
                    env_need_trans.append(env)

        if env_need_trans:
            self.log(
                f"🤖💬 Starting setting need_trans for project...⏳: {os.path.basename(self.project_dir)}."
            )

            placeholder_to_index = {
                env["placeholder"]: i for i, env in enumerate(latex_parser.envs_json)
            }

            for env in tqdm(
                env_need_trans,
                desc="Setting need trans",
                total=len(env_need_trans),
                unit="env",
            ):
                i = placeholder_to_index.get(env["placeholder"])
                if i is not None:
                    latex_parser.envs_json[i]["need_trans"] = (
                        self._request_llm_for_judge(
                            pm.set_need_trans_for_envs_system_prompt, env["content"]
                        )
                    )

        self.save_file(
            Path(self.output_dir, "inputs_map.json"), "json", latex_parser.inputs_json
        )
        self.save_file(
            Path(self.output_dir, "envs_map.json"), "json", latex_parser.envs_json
        )
        self.save_file(
            Path(self.output_dir, "captions_map.json"),
            "json",
            latex_parser.captions_json,
        )
        self.save_file(
            Path(self.output_dir, "newcommands_map.json"),
            "json",
            latex_parser.newcommands_json,
        )
        self.save_file(
            Path(self.output_dir, "sections_map.json"),
            "json",
            latex_parser.sections_json,
        )

        self.log(f"✅ Successfully parsed {os.path.basename(self.project_dir)}.")
        self.log(f"🤖💬 Parsed files are saved in {self.output_dir}.")

    # def _set_need_trans(self, env: Dict[str, Any]) -> Dict[str, Any]:
    #     """
    #     Determine whether translation is needed for the given environment.
    #     """
    #     # if not env.get("need_trans", False) and env.get("env_name", "") not in ['abstract', 'itemize']:

    #     set_env = env.copy()
    #     set_env["need_trans"] = self._request_llm_for_judge(
    #         set_need_trans_for_envs_system_prompt,
    #         set_env["content"]
    #     )
    #     return set_env

    def _build_judge_payload(self, system_prompt: str, text: str) -> Dict[str, Any]:
        """Construct the OpenAI-compatible payload for environment evaluation."""

        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "max_tokens": 50,
        }

    def _get_headers(self) -> Dict[str, str]:
        """Return authorization headers for OpenAI-compatible endpoints."""

        if not self.API_KEY:
            return {"Content-Type": "application/json"}
        return {
            "Authorization": f"Bearer {self.API_KEY}",
            "Content-Type": "application/json",
        }

    def _request_llm_for_judge(self, system_prompt: str, text: str) -> bool:
        """Run a lightweight LLM call to determine environment translation need."""

        payload = self._build_judge_payload(system_prompt, text)

        if self.use_ollama:
            if self.ollama_host is None or ollama is None:
                raise RuntimeError("Ollama host not configured correctly.")
            client = ollama.Client(host=self.ollama_host)
            response = client.chat(
                model=self.model,
                messages=payload["messages"],
                options={"temperature": 0, "num_ctx": 1024},
            )
            output = response["message"]["content"].strip().lower()
            return output == "true" or output not in {"false", "0"}

        if not self.base_url:
            raise ValueError(
                "base_url must be configured for non-Ollama LLM requests in ParserAgent"
            )

        headers = self._get_headers()

        for attempt in range(1, 4):
            try:
                response = requests.post(
                    self.base_url, json=payload, headers=headers, timeout=100
                )
                response.raise_for_status()
                result = response.json()
                output = result["choices"][0]["message"]["content"].strip().lower()

                if output == "true":
                    return True
                if output == "false":
                    return False
                return True
            except requests.exceptions.RequestException as e:
                if attempt < 3:
                    print(f"{e}")
                    time.sleep(3)
                else:
                    print("⚠️ Failed to Set need trans, set True.")
                    return True

        # Default fallback if all attempts fail
        return True
