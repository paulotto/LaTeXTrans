from typing import Dict, Any, List, Optional
from src.agents.tool_agents.base_tool_agent import BaseToolAgent
from src.formats.latex.prompts import *
from src.formats.latex.utils import *
from pathlib import Path
import sys
import os
import re
import regex
import requests
import time
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed


base_dir = os.getcwd()
sys.path.append(base_dir)

class TranslatorAgent_llama_qwen(BaseToolAgent):
    def __init__(self, 
                 config: Dict[str, Any], 
                 trans_mode: str = 0,
                 project_dir: Optional[str] = None,
                 output_dir: Optional[str] = None,
                 errors_report: Optional[List[Dict]] = None,
                 ):
        super().__init__(agent_name="TranslatorAgent", config=config)
        self.config = config
        self.model = config["llm_config"].get("model", "gpt-4o")
        self.base_url = config["llm_config"].get("base_url", None)
        self.API_KEY = config["llm_config"].get("api_key", None)
        self.target_language = config.get("target_language", "ch")
        self.project_dir = project_dir  # Project path for parsing
        self.output_dir = output_dir  # Output directory for parsed files
        self.fail_section_nums = []
        self.fail_caption_phs = []
        self.fail_env_phs = []
        self.have_fail_parts = False
        self.errors_report = errors_report if errors_report is not None else []
        self.trans_mode = trans_mode if trans_mode is not None else 0
        self.term_dict = config.get("term_dict", {})  # Dictionary for terminology translation
        self.summary = ''
        self.prev_text = ''
        self.prev_transed_text = ''
        self.currant_content = ''

    def execute(self):

        sections = self.read_file(Path(self.output_dir, "sections_map.json"), "json")
        from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

        # 加载模型
        model_name = "meta-llama/Llama-3.1-8B"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype="auto", device_map="auto")

        translator = pipeline("text-generation", model=model, tokenizer=tokenizer, max_new_tokens=8192)
        
        if self.trans_mode == 0 or self.trans_mode == 2:
            self.log(f"🤖💬 Starting translating for project...⏳: {os.path.basename(self.project_dir)}.")
            with ThreadPoolExecutor(max_workers=3) as executor:

                futures = [executor.submit(lambda i, sec: (i, self.translate(sec, translator)), i, sec) 
                        for i, sec in enumerate(sections)]

                for future in tqdm(as_completed(futures), total=len(futures), desc="Translating...", unit="section"):
                # for future in as_completed(futures):
                    # try:
                    i, translated_section = future.result()
                    sections[i] = translated_section
                    # except Exception as e:
                    #     self.log(f"❌ Error translating section: {e}")
                    self.save_file(Path(self.output_dir, "sections_map.json"), "json", sections)            
            
            self.log(f"✅ Successfully translated sections!")

    def translate(self, 
                  section: Dict[str, Any], translator: Any
                  ) -> Dict[str, Any]:
        """
        Translates the input data.
        translate section then envs and captions in this section
        """

        if section["section"] != "0" and section["section"] != "-1":
            section = self._translate_section(section, translator) # LaTexTrans
        # section = self._translate_section(section) # baseline

        return section



    def _translate_section(self, section: Dict[str, Any], translator) -> Dict[str, Any]:
        """
        Translates the sections of the input data.
        """
        transed_section = section.copy()
        if self.trans_mode == 0:
            try:
                transed_section["trans_content"] = self._request_llama( 
                                                            section["content"], translator=translator
                                                            )
            except Exception as e:
                print(e)
                transed_section["trans_content"] = section["content"]

        return transed_section

    def _request_llama(self, src: str, translator):

        # 固定的翻译说明（原本你作为 system prompt 用的）
        system_prompt = """
            You are a professional academic translator specializing in LaTeX-based scientific writing. 
            Your task is to translate a long LaTeX text (including chapter titles and text) provided by users from English to Chinese, while strictly maintaining the integrity of LaTeX syntax.
            Please strictly follow the following requirements when translating:
            1.Only translate the natural language content while keeping all LaTeX commands, environments, references, mathematical expressions, and labels unchanged.
            2.Section headings (e.g. natural content enclosed in {} in section identifiers like \section{}, \subsection{} and \subsubsection{}) must also be translated, but their LaTeX syntax must remain unchanged.
            3.Do not translate or modify the following LaTeX elements:
            Control commands: \label{}, \cite{}, \ref{}, \textbf{}, \emph{}, etc.
            Mathematical environments: $...$, \[…\], \begin{equation}...\end{equation}, etc.
            Any parameter or argument that includes numerical values with LaTeX layout units such as:
            em, ex, in, pt, pc, cm, mm, dd, cc, nd, nc, bp, sp. Example: \vspace{-1.125cm} or [scale=0.58] → leave such expressions completely unchanged.
            4.Do not change the writing of special characters, such as "\%", "\#", "\&", etc., to ensure that the translated text is accurate.
            5.For highlighting commands or style-related LaTeX commands (such as \hl{...}, \ctext[RGB]{...}{...}, and other custom commands based on soul, xcolor, etc.) that are known to fail with Chinese characters, do not translate their arguments. Keep the original English content inside these commands to ensure successful LaTeX compilation.
            6.Please add appropriate spaces before and after special symbols to ensure that after the translated code is compiled, the text will not be misaligned on the right side, which will affect the layout and format of the text. For example, when translating "|special_token|<reasoning_process>|special_token|<summary>", you may need to add appropriate spaces to become: "| special\_token| <reasoning\_process> | special\_token| <summary>", because if the text appears at the end of the line after compilation, it may be misaligned on the right side due to the inability to wrap.
            7.The final output must be a valid and compilable LaTeX document.
            8.Ensure that the translated text is accurate, coherent, and follows academic writing conventions in the target language.Maintain consistent academic terminology and use standard abbreviations where appropriate.
            9.Directly output only the translated LaTeX code without any additional explanations, formatting markers, or comments such as "```latex".
            10.<PLACEHOLDER_CAP_...>,<PLACEHOLDER_ENV_...>,<PLACEHOLDER_..._begin> and <PLACEHOLDER_..._end> are placeholders for artificial environments or captions. Please do not let them affect your translation and keep these placeholders after translation.
        """.strip()

        def build_llama_prompt(latex_segment: str) -> str:
            return f"""<|begin_of_text|><|start_header_id|>user<|end_header_id|>
        {system_prompt}

        Now, please translate the following LaTeX content:

        {latex_segment}
        <|start_header_id|>assistant<|end_header_id|>
        """

        def translate_latex_segment(segment: str) -> str:
            prompt = build_llama_prompt(segment)
            output = translator(prompt)[0]["generated_text"]
            # 提取 assistant 部分内容
            if "<|start_header_id|>assistant<|end_header_id|>" in output:
                output = output.split("<|start_header_id|>assistant<|end_header_id|>")[1]
            return output.strip()

        # 示例
        result = translate_latex_segment(src)
        return result

#         print(response_data)
# import toml
# import argparse

# parser = argparse.ArgumentParser()
# parser.add_argument("--config", type=str, default="config/default.toml")
# args = parser.parse_args()

# config = toml.load(args.config)

# trans_agent = TranslatorAgent(config)
# trans_agent.execute()

    