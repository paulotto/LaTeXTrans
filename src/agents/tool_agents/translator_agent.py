"""Translator tool agent orchestrating LaTeX-aware translation with LLM backends."""

from typing import Dict, Any, List, Optional
from src.agents.tool_agents.base_tool_agent import BaseToolAgent

# from TransLatex.src.formats.latex.prompts import *
import src.formats.latex.prompts as pm
from src.formats.latex.utils import (
    delete_ph,
    LatexNodes2Text,
    replace_href,
    replace_includegraphics,
)
from src.formats.latex.validation_utils import sanitize_translated_text
from pathlib import Path
import sys
import os
import re
import json
import asyncio
import aiohttp
import requests
import time
import pandas as pd
from tqdm import tqdm
import streamlit as st

# Add Ollama import with fallback
try:
    import ollama

    OLLAMA_AVAILABLE = True
except ImportError:
    ollama = None  # type: ignore[assignment]
    OLLAMA_AVAILABLE = False

base_dir = os.getcwd()
sys.path.append(base_dir)


class TranslatorAgent(BaseToolAgent):
    """Coordinates translation of LaTeX sources by delegating to LLM APIs."""

    def __init__(
        self,
        config: Dict[str, Any],
        project_dir: str,
        output_dir: str,
        trans_mode: int = 0,
        errors_report: Optional[List[Dict]] = None,
    ):
        """Initialize a translator agent with runtime configuration.

        Parameters
        ----------
        config:
            Nested configuration dictionary loaded from the runner, containing
            LLM credentials, prompts, and optional terminology settings.
        project_dir:
            Absolute path to the original LaTeX project being translated.
        output_dir:
            Directory where intermediate JSON maps and translated artifacts live.
        trans_mode:
            Execution mode for translation: ``0`` full translate, ``1`` retry
            failed parts only, ``2`` terminology-aware translation.
        errors_report:
            Optional list with structured information about failed segments that
            require a re-translation pass.
        """

        super().__init__(agent_name="TranslatorAgent", config=config)

        self.config = config
        if config.get("update_term") == "True":
            self.update_term = True
            self.update_term = False
        # self.update_term = config.get("update_term", False)
        self.model = config["llm_config"].get("model", "gpt-4o")
        self.base_url = config["llm_config"].get("base_url", None)
        self.API_KEY = config["llm_config"].get("api_key", None)
        self.user_term = config.get("user_term", None)
        self.target_language = config.get("target_language", "ch")
        self.category = config.get("category", None)

        # Detect if using Ollama
        self.use_ollama = self._is_ollama_endpoint()
        self.ollama_client = None
        self.ollama_host = None
        if self.use_ollama and not OLLAMA_AVAILABLE:
            raise ImportError(
                "Ollama package not installed. Please install with: pip install ollama"
            )

        # Initialize Ollama client if needed
        if self.use_ollama:
            assert ollama is not None  # for type checkers
            self.ollama_host = (
                self.base_url.replace("/v1/chat/completions", "")
                if self.base_url
                else "http://localhost:11434"
            )
            self.ollama_client = ollama.AsyncClient(host=self.ollama_host)

        self.project_dir = project_dir  # Project path for parsing
        self.output_dir = output_dir  # Output directory for parsed files
        self.fail_section_nums = []
        self.fail_caption_phs = []
        self.fail_env_phs = []
        self.have_fail_parts = False
        self.errors_report = errors_report if errors_report is not None else []
        self.trans_mode = trans_mode if trans_mode is not None else 0
        # self.term_dict = config.get("term_dict", {})  # Dictionary for terminology translation
        self.term_dict = {}
        self.summary = ""
        self.prev_text = ""
        self.prev_transed_text = ""
        self.currant_content = ""

    def _is_ollama_endpoint(self) -> bool:
        """Return ``True`` when the configured base URL targets an Ollama host."""
        if not self.base_url:
            return False
        return "localhost:11434" in self.base_url or "ollama" in self.base_url.lower()

    def _build_chat_payload(
        self, system_prompt: str, user_content: str
    ) -> Dict[str, Any]:
        """Create the OpenAI-compatible payload shared by sync and async calls."""

        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.7,
            "max_new_tokens": 8192,
        }

    def _get_auth_headers(self) -> Dict[str, str]:
        """Build authorization headers for OpenAI-compatible APIs."""

        return {
            "Authorization": f"Bearer {self.API_KEY}",
            "Content-Type": "application/json",
        }

    async def _make_llm_request(
        self,
        system_prompt: str,
        user_content: str,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> str:
        """Call the configured LLM asynchronously, honoring pooled sessions.

        Parameters
        ----------
        system_prompt:
            Prompt injected as the system role for the chat completion.
        user_content:
            Primary message describing the translation task.
        session:
            Optional externally-managed :class:`aiohttp.ClientSession`. When not
            provided, a short-lived session is created for the single request.

        Returns
        -------
        str
            Raw assistant message produced by the backend.
        """

        if self.use_ollama:
            # Use Ollama client
            if self.ollama_client is None:
                raise aiohttp.ClientError("Ollama client not initialized.")
            try:
                response = await self.ollama_client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    options={"temperature": 0.7, "num_ctx": 8192},
                )
                return response["message"]["content"].strip()
            except Exception as e:
                raise aiohttp.ClientError(f"Ollama request failed: {e}")

        payload = self._build_chat_payload(system_prompt, user_content)
        headers = self._get_auth_headers()

        async def _post(session_obj: aiohttp.ClientSession) -> str:
            async with session_obj.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=100),
            ) as response:
                response.raise_for_status()
                result = await response.json()
                return result["choices"][0]["message"]["content"].strip()

        if session is not None:
            return await _post(session)

        async with aiohttp.ClientSession() as temp_session:
            return await _post(temp_session)

    def _make_llm_request_sync(self, system_prompt: str, user_content: str) -> str:
        """Perform a blocking LLM request using either Ollama or OpenAI APIs."""

        if self.use_ollama:
            if not self.ollama_host or ollama is None:
                raise RuntimeError("Ollama host not configured.")
            try:
                sync_client = ollama.Client(host=self.ollama_host)
                response = sync_client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    options={"temperature": 0.7, "num_ctx": 8192},
                )
                return response["message"]["content"].strip()
            except Exception as e:
                raise RuntimeError(f"Ollama request failed: {e}") from e

        payload = self._build_chat_payload(system_prompt, user_content)
        headers = self._get_auth_headers()

        response = requests.post(
            self.base_url,
            json=payload,
            headers=headers,
            timeout=100,
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()

    def _clean_translated_text(self, text: str) -> str:
        """Remove reasoning artifacts and leading chatter before LaTeX commands."""

        return sanitize_translated_text(text)

    async def execute(self, data=None, error_retry_count=0, Maxtry=3, **kwargs):
        """Entry point invoked by the coordinator to launch translation.

        Parameters
        ----------
        data:
            Placeholder for future inputs (currently unused).
        error_retry_count:
            Number of times error-driven retranslation has already run.
        Maxtry:
            Upper bound for retries when certain sections keep failing.
        kwargs:
            Reserved for custom overrides from the orchestration layer.
        """
        pm.init_prompts(self.config["source_language"], self.config["target_language"])
        self.add_placeholder()
        self.build_term_dict()

        sys.stderr = open(os.devnull, "w")
        process_b = st.empty()
        with process_b:
            process_bar = st.progress(0)
        status_text = st.empty()
        sys.stderr = sys.__stderr__

        sections = self.read_file(Path(self.output_dir, "sections_map.json"), "json")
        captions = self.read_file(Path(self.output_dir, "captions_map.json"), "json")
        envs = self.read_file(Path(self.output_dir, "envs_map.json"), "json")

        if self.trans_mode == 0 or self.trans_mode == 2:
            self.log(
                f"🤖💬 Starting translating for project...⏳: {os.path.basename(self.project_dir)}."
            )

            sys.stderr = open(os.devnull, "w")
            status_text.text(
                f"🤖💬 Starting translating for project...⏳: {os.path.basename(self.project_dir)}."
            )
            process_bar.progress(5)
            sys.stderr = sys.__stderr__

            async with aiohttp.ClientSession() as session:
                sem = asyncio.Semaphore(
                    10
                )  # Considering the api response speed, processing one section approximately takes about 10 seconds, and initiating a call every half second,
                # around 10 should not waste api tokens

                async def process_section(i, sec):
                    async with sem:
                        translated = await self.translate(sec, envs, captions, session)
                        return i, translated

                tasks = [process_section(i, sec) for i, sec in enumerate(sections)]

                completed = 0

                for future in tqdm(
                    asyncio.as_completed(tasks),
                    total=len(tasks),
                    desc="Translating...",
                    unit="section",
                ):
                    i, translated_section = await future
                    sections[i] = translated_section

                    completed += 1

                    sys.stderr = open(os.devnull, "w")
                    process = int(5 + 90 * completed / len(tasks))
                    process_bar.progress(process)
                    sys.stderr = sys.__stderr__

                    # It can be considered to save and modify to integrate memory once for hard memory read and write,
                    # and save each section once for the convenience of observing the translation situation.
                    self.save_file(
                        Path(self.output_dir, "sections_map.json"), "json", sections
                    )
                    self.save_file(
                        Path(self.output_dir, "captions_map.json"), "json", captions
                    )
                    self.save_file(Path(self.output_dir, "envs_map.json"), "json", envs)

                sys.stderr = open(os.devnull, "w")
                status_text.text("🔍 Validating translation results ..")
                process_bar.progress(95)
                sys.stderr = sys.__stderr__

                await self._val_fail_parts(
                    Maxtry=Maxtry,
                    sections=sections,
                    captions=captions,
                    envs=envs,
                    session=session,
                )

                self.log("✅ Successfully translated sections!")

                sys.stderr = open(os.devnull, "w")
                status_text.text("✅ Successfully translated sections!")
                process_bar.progress(100)
                st.success("✅ Successfully translated sections!")
                process_b.empty()
                status_text.empty()
                sys.stderr = sys.__stderr__

        elif self.trans_mode == 1:
            sys.stderr = open(os.devnull, "w")
            status_text = st.empty()
            sys.stderr = sys.__stderr__
            async with aiohttp.ClientSession() as session:
                error_parts = [
                    error_part["num_or_ph"] for error_part in self.errors_report
                ]
                self.log(
                    f"🤖💬 Starting retranslating for error parts:{error_parts}, the {error_retry_count + 1} chance for {Maxtry} total."
                )
                sys.stderr = open(os.devnull, "w")
                status_text.text(
                    f"🤖💬 Starting retranslating for error parts:{error_parts}, the {error_retry_count + 1} chance for {Maxtry} total."
                )
                sys.stderr = sys.__stderr__
                await self._retranslate_error_parts(
                    secs=sections, caps=captions, envs=envs, session=session
                )

                self.save_file(
                    Path(self.output_dir, "sections_map.json"), "json", sections
                )
                self.save_file(
                    Path(self.output_dir, "captions_map.json"), "json", captions
                )
                self.save_file(Path(self.output_dir, "envs_map.json"), "json", envs)

                self.fail_section_nums.clear()
                self.fail_caption_phs.clear()
                self.fail_env_phs.clear()
                self.have_fail_parts = False

                await self._val_fail_parts(
                    Maxtry=Maxtry,
                    sections=sections,
                    captions=captions,
                    envs=envs,
                    session=session,
                )

            self.log("✅ Successfully retranslated error parts!")
            sys.stderr = open(os.devnull, "w")
            status_text.text("✅ Successfully retranslated error parts!")
            time.sleep(3)
            status_text.empty()
            sys.stderr = sys.__stderr__

    async def translate(
        self,
        section: Dict[str, Any],
        envs: List[Dict[str, Any]],
        captions: List[Dict[str, Any]],
        session: aiohttp.ClientSession,
    ) -> Dict[str, Any]:
        """Translate a section and its dependent environments/captions.

        Parameters
        ----------
        section:
            Structured map with raw LaTeX content and metadata.
        envs:
            Collection of environment placeholders that may require translation.
        captions:
            Collection sharing caption placeholders tied to figures/tables.
        session:
            Shared :class:`aiohttp.ClientSession` used for outbound LLM calls.

        Returns
        -------
        dict
            The updated section record with translated content merged in.
        """
        placeholder_pattern_cap = r"<PLACEHOLDER_CAP_\d+>"
        placeholder_pattern_env = r"<PLACEHOLDER_ENV_\d+>"
        placeholders_cap = re.findall(placeholder_pattern_cap, section["content"])
        placeholders_env = re.findall(placeholder_pattern_env, section["content"])

        if section["section"] == "-1" or section["section"] == "0":
            section = section
        else:
            section = await self._translate_section(section, session)

        for placeholder in placeholders_env:
            for i, env in enumerate(envs):
                if placeholder == env["placeholder"]:
                    placeholders_cap_in_env = re.findall(
                        placeholder_pattern_cap, env["content"]
                    )
                    placeholders_cap.extend(placeholders_cap_in_env)
                    envs[i] = await self._translate_env(env, session)
                    break

        # remove duplicates
        placeholders_cap = list(dict.fromkeys(placeholders_cap))

        for placeholder in placeholders_cap:
            for i, caption in enumerate(captions):
                if placeholder == caption["placeholder"]:
                    captions[i] = await self._translate_caption(caption, session)
                    break

        return section

    async def _val_fail_parts(
        self,
        sections,
        captions,
        envs,
        Maxtry,
        session: aiohttp.ClientSession,
        fail_retry_count=0,
    ) -> None:
        """Retry translation for failed parts until success or the retry cap.

        Parameters
        ----------
        sections, captions, envs:
            Mutable translation maps updated in-place as retries succeed.
        Maxtry:
            Maximum number of retry cycles allowed.
        session:
            Session used to perform the asynchronous LLM requests.
        fail_retry_count:
            Counter tracking the current retry attempt.
        """
        sys.stderr = open(os.devnull, "w")
        status_text = st.empty()
        sys.stderr = sys.__stderr__
        while fail_retry_count < Maxtry and self.have_fail_parts:
            fail_parts = (
                self.fail_section_nums + self.fail_caption_phs + self.fail_env_phs
            )
            if fail_retry_count == Maxtry:  #  retry 3 times
                print(f"❌ Failed to translate {fail_parts}")
                sys.stderr = open(os.devnull, "w")
                status_text.error(f"❌ Failed to translate {fail_parts}")
                st.error(f"❌ Failed to translate {fail_parts}")
                time.sleep(3)
                sys.stderr = sys.__stderr__
                break
            self.log(
                f"🤖💬 Starting retranslating for fail parts:{fail_parts}, the {fail_retry_count + 1} chance for {Maxtry} total."
            )
            sys.stderr = open(os.devnull, "w")
            status_text.text(
                f"🤖💬 Starting retranslating for fail parts:{fail_parts}, the {fail_retry_count + 1} chance for {Maxtry} total."
            )
            sys.stderr = sys.__stderr__
            await self._retranslate_fail_parts(
                secs=sections, caps=captions, envs=envs, session=session
            )
            self.save_file(Path(self.output_dir, "sections_map.json"), "json", sections)
            self.save_file(Path(self.output_dir, "captions_map.json"), "json", captions)
            self.save_file(Path(self.output_dir, "envs_map.json"), "json", envs)

            fail_retry_count += 1
            sys.stderr = open(os.devnull, "w")
            time.sleep(3)
            status_text = st.empty()
            sys.stderr = sys.__stderr__

    async def _retranslate_fail_parts(
        self,
        secs: List[Dict[str, Any]],
        caps: List[Dict[str, Any]],
        envs: List[Dict[str, Any]],
        session: aiohttp.ClientSession,
    ) -> Any:
        """Re-run translation for parts recorded in the failure queues.

        Parameters
        ----------
        secs, caps, envs:
            Translation maps whose failing entries will be mutated in-place.
        session:
            Session used to issue the correction requests.

        Returns
        -------
        Any
            Legacy return value preserved for backward compatibility.
        """
        sec_nums = self.fail_section_nums[:]
        cap_phs = self.fail_caption_phs[:]
        env_phs = self.fail_env_phs[:]
        self.fail_section_nums.clear()
        self.fail_caption_phs.clear()
        self.fail_env_phs.clear()
        self.have_fail_parts = False

        sec_dict = {s["section"]: i for i, s in enumerate(secs)}
        cap_dict = {c["placeholder"]: i for i, c in enumerate(caps)}
        env_dict = {e["placeholder"]: i for i, e in enumerate(envs)}

        if sec_nums:
            self.log(f"Retranslating for {sec_nums}")
            for sec_num in sec_nums:
                if sec_num == "-1" or sec_num == "0":
                    continue
                if sec_num in sec_dict:
                    i = sec_dict[sec_num]
                    secs[i] = await self._translate_section(secs[i], session)
            # else:
            #     print(f"[Warning] Section {sec_num} not found.")
        if cap_phs:
            self.log(f"Retranslating for {cap_phs}")
            for cap_ph in cap_phs:
                if cap_ph in cap_dict:
                    i = cap_dict[cap_ph]
                    caps[i] = await self._translate_caption(caps[i], session)
            # else:
            #     print(f"[Warning] Caption placeholder {cap_ph} not found.")
        if env_phs:
            self.log(f"Retranslating for {env_phs}")
            for env_ph in env_phs:
                if env_ph in env_dict:
                    i = env_dict[env_ph]
                    envs[i] = await self._translate_env(envs[i], session)
            # else:
            #     print(f"[Warning] Environment placeholder {env_ph} not found.")

    async def _retranslate_error_parts(self, secs, caps, envs, session) -> Any:
        """Handle targeted retranslation jobs created during validation.

        Parameters
        ----------
        secs, caps, envs:
            Translation maps which will be mutated with improved content.
        session:
            Session used for API calls during the retry sweep.

        Returns
        -------
        Any
            Mirrors previous behaviour; kept for compatibility with callers.
        """
        async with aiohttp.ClientSession() as session:
            sem = asyncio.Semaphore(20)

            sys.stderr = open(os.devnull, "w")
            process_b = st.empty()
            with process_b:
                process_bar = process_b.progress(0)
            status_text = st.empty()
            sys.stderr = sys.__stderr__
            completed = 0

            async def process_ErrorPart(i, error_report):
                async with sem:
                    error_message = []
                    if "command_error" in error_report:
                        error_message.append(error_report["command_error"])
                    if "ph_error" in error_report:
                        error_message.append(error_report["ph_error"])
                    if "bracket_error" in error_report:
                        error_message.append(error_report["bracket_error"])
                    error_message = "\n".join(error_message)

                    if error_report["part"] == "sec":

                        async def process_section(i, sec):
                            async with sem:
                                if error_report["num_or_ph"] == sec["section"]:
                                    sec_async = await self._translate_section(
                                        section=sec,
                                        error_message=error_message,
                                        session=session,
                                    )
                                    return {
                                        "index": i,
                                        "result": sec_async,
                                        "is_valid": True,
                                    }
                                else:
                                    return {
                                        "index": None,
                                        "result": None,
                                        "is_valid": False,
                                    }

                        tasks_sec = [
                            process_section(i, sec) for i, sec in enumerate(secs)
                        ]
                        for future in asyncio.as_completed(tasks_sec):
                            result = await future

                            if result["is_valid"]:
                                i = result["index"]
                                _sec = result["result"]
                                secs[i] = _sec
                    elif error_report["part"] == "env":

                        async def process_env(i, env):
                            async with sem:
                                if error_report["num_or_ph"] == env["placeholder"]:
                                    env_async = await self._translate_env(
                                        env=env,
                                        error_message=error_message,
                                        session=session,
                                    )
                                    return {
                                        "index": i,
                                        "result": env_async,
                                        "is_valid": True,
                                    }
                                else:
                                    return {
                                        "index": None,
                                        "result": None,
                                        "is_valid": False,
                                    }

                        tasks_env = [process_env(i, env) for i, env in enumerate(envs)]
                        for future in asyncio.as_completed(tasks_env):
                            result = await future

                            if result["is_valid"]:
                                i = result["index"]
                                _env = result["result"]
                                envs[i] = _env
                    elif error_report["part"] == "cap":

                        async def process_cap(i, cap):
                            async with sem:
                                if error_report["num_or_ph"] == cap["placeholder"]:
                                    cap_async = await self._translate_caption(
                                        caption=cap,
                                        error_message=error_message,
                                        session=session,
                                    )
                                    return {
                                        "index": i,
                                        "result": cap_async,
                                        "is_valid": True,
                                    }
                                else:
                                    return {
                                        "index": None,
                                        "result": None,
                                        "is_valid": False,
                                    }

                        tasks_cap = [process_cap(i, cap) for i, cap in enumerate(caps)]
                        for future in asyncio.as_completed(tasks_cap):
                            result = await future

                            if result["is_valid"]:
                                i = result["index"]
                                _cap = result["result"]
                                caps[i] = _cap
                    return i

            tasks_ErrorPart = [
                process_ErrorPart(i, error_report)
                for i, error_report in enumerate(self.errors_report)
            ]
            for future in tqdm(
                asyncio.as_completed(tasks_ErrorPart),
                total=len(tasks_ErrorPart),
                desc="Translating...",
                unit="section",
            ):
                result = await future
                completed += 1
                sys.stderr = open(os.devnull, "w")
                process_bar.progress(completed / len(tasks_ErrorPart))
                status_text.text(
                    f"Completed {completed}/{len(tasks_ErrorPart)} part（{completed / len(tasks_ErrorPart):.1%}）"
                )
                sys.stderr = sys.__stderr__

                if result is not None:
                    # Result indicates which error part finished, kept for potential debugging
                    pass

            sys.stderr = open(os.devnull, "w")
            process_bar.progress(100)
            status_text.text("Complete a retranslation once")
            time.sleep(3)
            process_b.empty()
            status_text.empty()
            sys.stderr = sys.__stderr__

    async def _translate_section(
        self,
        section: Dict[str, Any],
        session: aiohttp.ClientSession,
        error_message="None",
    ) -> Dict[str, Any]:
        """Translate a single section record according to the active mode.

        Parameters
        ----------
        section:
            Section dictionary containing original content and metadata.
        session:
            Session used for the async LLM request.
        error_message:
            Optional contextual error details when retrying failed parts.

        Returns
        -------
        dict
            Copy of the section dictionary augmented with ``trans_content``.
        """
        transed_section = section.copy()
        section_num = section["section"]
        if self.trans_mode == 0:
            transed_section["trans_content"] = await self._request_llm_for_trans(
                pm.section_system_prompt,
                section["content"],
                fail_part=section_num,
                type="sec",
                session=session,
            )
        elif self.trans_mode == 1:
            transed_section[
                "trans_content"
            ] = await self._request_llm_for_retrans_error_parts(
                pm.retrans_error_parts_system_prompt,
                part=transed_section,
                error_message=error_message,
                fail_part=section_num,
                type="sec",
                session=session,
            )

        elif self.trans_mode == 2:
            """
            Combined with terminology translation
            """
            if not self.term_dict:
                transed_section["trans_content"] = await self._request_llm_for_trans(
                    pm.section_system_prompt,
                    section["content"],
                    fail_part=section_num,
                    type="sec",
                    session=session,
                )
            else:
                transed_section[
                    "trans_content"
                ] = await self._request_llm_for_trans_with_terms(
                    pm.section_system_prompt_with_dict,
                    section["content"],
                    fail_part=section_num,
                    type="sec",
                    session=session,
                )

            try:
                if self.update_term:
                    src_text = self._extract_text_from_tex(transed_section["content"])
                    tgt_text = self._extract_text_from_tex(
                        transed_section["trans_content"]
                    )
                    term_text = await self._request_llm_for_extract_terms(
                        pm.extract_terminology_system_prompt,
                        src_text,
                        tgt_text,
                        session=session,
                    )

                    # self._updated_term_dict(term_text)
                    self._updated_term_dict_v2(term_text)
            except Exception as exc:
                self.log(
                    f"⚠️ Failed to update terminology for section {section_num}: {exc}"
                )
                return transed_section

        return transed_section

    async def _translate_caption(
        self,
        caption: Dict[str, Any],
        session: aiohttp.ClientSession,
        error_message="None",
    ) -> Dict[str, Any]:
        """Translate a caption, preserving glossary constraints when enabled.

        Parameters
        ----------
        caption:
            Caption record including original content and placeholder.
        session:
            Session used to communicate with the LLM endpoint.
        error_message:
            Optional explanation from the validator when retrying a failure.

        Returns
        -------
        dict
            Caption dictionary with ``trans_content`` populated.
        """
        transed_caption = caption.copy()
        placeholder = caption["placeholder"]
        if self.trans_mode == 0:
            transed_caption["trans_content"] = await self._request_llm_for_trans(
                pm.caption_system_prompt,
                caption["content"],
                fail_part=placeholder,
                type="cap",
                session=session,
            )
        elif self.trans_mode == 1:
            """先不改"""
            print("translate_caption_mode_1")
            transed_caption[
                "trans_content"
            ] = await self._request_llm_for_retrans_error_parts(
                pm.retrans_error_parts_system_prompt,
                part=transed_caption,
                error_message=error_message,
                fail_part=placeholder,
                type="cap",
                session=session,
            )

        elif self.trans_mode == 2:
            if not self.term_dict:
                transed_caption["trans_content"] = await self._request_llm_for_trans(
                    pm.caption_system_prompt,
                    caption["content"],
                    fail_part=placeholder,
                    type="cap",
                    session=session,
                )
            else:
                transed_caption[
                    "trans_content"
                ] = await self._request_llm_for_trans_with_terms(
                    pm.caption_system_prompt_with_dict,
                    caption["content"],
                    fail_part=placeholder,
                    type="cap",
                    session=session,
                )
            try:
                if self.update_term:
                    src_text = self._extract_text_from_tex(transed_caption["content"])
                    tgt_text = self._extract_text_from_tex(
                        transed_caption["trans_content"]
                    )
                    term_text = await self._request_llm_for_extract_terms(
                        pm.extract_terminology_system_prompt,
                        src_text,
                        tgt_text,
                        session=session,
                    )

                    # self._updated_term_dict(term_text)
                    self._updated_term_dict_v2(term_text)
            except Exception as exc:
                self.log(
                    f"⚠️ Failed to update terminology for caption {placeholder}: {exc}"
                )
                return transed_caption

        return transed_caption

    async def _translate_env(
        self, env: Dict[str, Any], session: aiohttp.ClientSession, error_message="None"
    ) -> Dict[str, Any]:
        """Translate an environment block when marked as needing translation.

        Parameters
        ----------
        env:
            Environment record describing the LaTeX block and placeholder.
        session:
            Session used for outbound asynchronous API calls.
        error_message:
            Optional validation feedback used during retries.

        Returns
        -------
        dict
            Environment record copied with translated content filled in.
        """
        transed_env = env.copy()
        placeholder = env["placeholder"]
        if self.trans_mode == 0:  # sum
            if env["need_trans"]:
                transed_env["trans_content"] = await self._request_llm_for_trans(
                    pm.env_system_prompt,
                    env["content"],
                    fail_part=placeholder,
                    type="env",
                    session=session,
                )
            else:
                transed_env["trans_content"] = env["content"]
        elif self.trans_mode == 1:
            transed_env[
                "trans_content"
            ] = await self._request_llm_for_retrans_error_parts(
                pm.retrans_error_parts_system_prompt,
                part=transed_env,
                error_message=error_message,
                fail_part=placeholder,
                type="env",
                session=session,
            )
        elif self.trans_mode == 2:  # dict or sum+dict
            if not self.term_dict:
                if env["need_trans"]:
                    transed_env["trans_content"] = await self._request_llm_for_trans(
                        pm.env_system_prompt,
                        env["content"],
                        fail_part=placeholder,
                        type="env",
                        session=session,
                    )
                else:
                    transed_env["trans_content"] = env["content"]
            else:
                if env["need_trans"]:
                    transed_env[
                        "trans_content"
                    ] = await self._request_llm_for_trans_with_terms(
                        pm.env_system_prompt_with_dict,
                        env["content"],
                        fail_part=placeholder,
                        type="env",
                        session=session,
                    )
                else:
                    transed_env["trans_content"] = env["content"]

            if env["need_trans"]:
                try:
                    if self.update_term:
                        src_text = self._extract_text_from_tex(transed_env["content"])
                        tgt_text = self._extract_text_from_tex(
                            transed_env["trans_content"]
                        )
                        text = await self._request_llm_for_extract_terms(
                            pm.extract_terminology_system_prompt,
                            src_text,
                            tgt_text,
                            session=session,
                        )

                        # self._updated_term_dict(term_text)
                        self._updated_term_dict_v2(text)
                except Exception as exc:
                    self.log(
                        f"⚠️ Failed to update terminology for environment {placeholder}: {exc}"
                    )
                    return transed_env

        return transed_env

    async def _request_llm_for_trans(
        self,
        system_prompt: str,
        text: str,
        fail_part: str,
        type: str,
        session: aiohttp.ClientSession,
    ) -> str:
        """Submit a translation request and capture the assistant response.

        Parameters
        ----------
        system_prompt:
            Prompt providing translation instructions for the LLM.
        text:
            Raw LaTeX snippet to translate.
        fail_part:
            Identifier (section number or placeholder) used when logging failures.
        type:
            Categorises the text (``sec``, ``cap``, ``env``) for retry bookkeeping.
        session:
            Session issuing the asynchronous HTTP call.

        Returns
        -------
        str
            Translated content or the original text upon repeated failures.
        """
        for attempt in range(1, 4):
            try:
                raw = await self._make_llm_request(system_prompt, text, session)
                return self._clean_translated_text(raw)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < 3:
                    await asyncio.sleep(5)
                else:
                    self.have_fail_parts = True
                    if type == "sec":
                        self.fail_section_nums.append(fail_part)
                    elif type == "cap":
                        self.fail_caption_phs.append(fail_part)
                    else:
                        self.fail_env_phs.append(fail_part)

                    print(
                        f"❌ Failed to translate text, return the original text:{fail_part}. {e}"
                    )
                    return text

        return "N/A"

    async def _request_llm_for_trans_with_terms(
        self,
        system_prompt: str,
        text: str,
        fail_part: str,
        type: str,
        session: aiohttp.ClientSession,
    ) -> str:
        """Translate text while enforcing terminology substitutions.

        Parameters
        ----------
        system_prompt:
            Prompt template that includes instructions for term adherence.
        text:
            LaTeX snippet to translate.
        fail_part:
            Identifier used when logging a failed translation attempt.
        type:
            Indicates whether the snippet is a section, caption or environment.
        session:
            Session responsible for executing the HTTP call.

        Returns
        -------
        str
            Translated content or original snippet if retries exhaust.
        """
        enhanced_prompt = f"{system_prompt}\nWhen translating, you must strictly use the following glossary for substitution. This is the highest priority rule to ensure the consistency of terms throughout the text.\n<Glossary>:\n{self.term_dict}\nNow, please translate the following new paragraph. Maintain the terminology from the glossary provided. If there was no text to begin with (e.g., an empty caption), return an empty string."
        user_content = f"[Current LaTeX Paragraph]:\n{text}"

        for attempt in range(1, 4):
            try:
                raw = await self._make_llm_request(
                    enhanced_prompt, user_content, session
                )
                return self._clean_translated_text(raw)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < 3:
                    await asyncio.sleep(5)
                else:
                    self.have_fail_parts = True
                    if type == "sec":
                        self.fail_section_nums.append(fail_part)
                    elif type == "cap":
                        self.fail_caption_phs.append(fail_part)
                    else:
                        self.fail_env_phs.append(fail_part)

                    print(
                        f"❌ Failed to translate text, return the original text:{fail_part}. {e}"
                    )
                    return text

        return "N/A"

    async def _request_llm_for_retrans_error_parts(
        self,
        system_prompt: str,
        part: Dict[str, Any],
        error_message: str,
        fail_part: str,
        type: str,
        session: aiohttp.ClientSession,
    ) -> str:
        """Re-translate a previously failed part with error diagnostics.

        Parameters
        ----------
        system_prompt:
            Prompt tailored for retry scenarios.
        part:
            Original translation record containing source and prior output.
        error_message:
            Validator feedback describing the failure mode.
        fail_part:
            Identifier (section index or placeholder) for logging.
        type:
            Category of the part (``sec``, ``cap``, ``env``).
        session:
            Session used to invoke the LLM asynchronously.

        Returns
        -------
        str
            Improved translation or the existing translation on repeated failure.
        """
        enhanced_prompt = f"{system_prompt}\nWhen translating, you must strictly use the following glossary for substitution. This is the highest priority rule to ensure the consistency of terms throughout the text.\n<Glossary>:\n{self.term_dict}\nNow, please translate the following new paragraph. Maintain the terminology from the glossary provided."
        user_content = f"[Original]:\n{part['content']}\n[Translation]:\n{part['trans_content']}\n[Error]:\n{error_message}"

        for attempt in range(1, 4):
            try:
                raw = await self._make_llm_request(
                    enhanced_prompt, user_content, session
                )
                return self._clean_translated_text(raw)
            except (
                requests.exceptions.RequestException,
                aiohttp.ClientError,
                asyncio.TimeoutError,
            ) as e:
                if attempt < 3:
                    await asyncio.sleep(5)
                else:
                    self.have_fail_parts = True
                    if type == "sec":
                        self.fail_section_nums.append(fail_part)
                    elif type == "cap":
                        self.fail_caption_phs.append(fail_part)
                    else:
                        self.fail_env_phs.append(fail_part)

                    print(
                        f"❌ Failed to translate text, return the original text:{fail_part}. {e}"
                    )
                    return part["trans_content"]

        return "N/A"

    async def _request_llm_for_extract_terms(
        self, system_prompt, src, tgt, session: aiohttp.ClientSession
    ) -> str:
        """Ask the LLM to mine candidate bilingual terminology pairs.

        Parameters
        ----------
        system_prompt:
            Prompt encouraging the assistant to extract terminology.
        src:
            Plain-text source segment.
        tgt:
            Corresponding translation segment.
        session:
            Session utilized for the asynchronous call.

        Returns
        -------
        str
            Raw assistant output, typically a list of "source - target" lines.
        """
        user_content = f"<en source>\n{src}\n<zh translation>\n{tgt}"

        for attempt in range(1, 4):
            try:
                return await self._make_llm_request(
                    system_prompt, user_content, session
                )
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt < 3:
                    self.log(f"⚠️ Term extraction attempt failed: {exc}")
                    await asyncio.sleep(5)
                else:
                    print("⚠️ Failed to extract terms, set N/A.")
                    return "N/A"

        return "N/A"

    def _request_llm_for_summary(self, system_prompt: str, text: str) -> str:
        """Generate a fresh summary for the accumulated translated content.

        Parameters
        ----------
        system_prompt:
            Prompt instructing the model on summary structure and tone.
        text:
            Combined content to condense.

        Returns
        -------
        str
            Generated summary text, or ``"N/A"`` if all attempts fail.
        """
        user_content = f"<Text to summarize>:\n{text}\n<Summary>:\n"

        for attempt in range(1, 4):
            try:
                return self._make_llm_request_sync(system_prompt, user_content)
            except (requests.exceptions.RequestException, RuntimeError) as e:
                if attempt < 3:
                    print(f"{e}")
                    time.sleep(3)
                else:
                    print("⚠️ Failed to summarize text, set N/A.")
                    return "N/A"

        return "N/A"

    def _request_llm_for_refine_summary(
        self, system_prompt: str, text: str, sum: str
    ) -> str:
        """Refine an existing summary with incremental section content.

        Parameters
        ----------
        system_prompt:
            Prompt explaining how to blend prior summary with new context.
        text:
            New section text to incorporate.
        sum:
            Existing summary prior to refinement.

        Returns
        -------
        str
            Updated summary, or ``"N/A"`` if the process fails repeatedly.
        """
        user_content = (
            f"<prev_summary>:\n{sum}\n<new_section>:\n{text}\n<refined_summary>:\n"
        )

        for attempt in range(1, 4):
            try:
                return self._make_llm_request_sync(system_prompt, user_content)
            except (requests.exceptions.RequestException, RuntimeError) as e:
                if attempt < 3:
                    print(f"{e}")
                    time.sleep(3)
                else:
                    print("⚠️ Failed to refine summary, set N/A.")
                    return "N/A"

        return "N/A"

    def _updated_term_dict(self, text: str) -> None:
        """Parse bilingual pairs from the LLM output and update glossary.

        Parameters
        ----------
        text:
            Assistant output expected to contain ``"source" - "target"`` pairs.
        """
        pattern = r'"([^"]+)"\s*-\s*"([^"]+)"'
        matches = re.findall(pattern, text)

        seen_lower = {k.lower() for k in self.term_dict}

        for en, zh in matches:
            en_lower = en.lower()
            if en_lower not in seen_lower:
                self.term_dict[en] = zh
                seen_lower.add(en_lower)

        self.save_file(Path(self.output_dir, "term_dict.json"), "json", self.term_dict)

    def _updated_term_dict_v2(self, text: str) -> None:
        """Improve glossary merging by tolerating malformed LLM lists.

        Parameters
        ----------
        text:
            Free-form assistant response potentially containing term pairs.
        """
        new_term_dict = {}
        lines = text.split("\n")[1:]
        for line in lines:
            line = line.strip()
            if not line:
                continue

            match = re.match(r'^"(.+?)"\s*-\s*"(.+?)"$', line)
            if match:
                english = match.group(1)
                chinese = match.group(2)
                new_term_dict[english] = chinese

        for en, zh in new_term_dict.items():
            if en not in self.term_dict:
                self.term_dict[en] = zh

    def _process_latex_to_eva(self, latex_code):
        """Normalize LaTeX snippets before extracting plain text.

        Parameters
        ----------
        latex_code:
            Raw LaTeX string subject to search/replace cleanup.

        Returns
        -------
        str
            Pre-processed LaTeX ready for text extraction.
        """
        latex_code = replace_href(latex_code)
        latex_code = replace_includegraphics(latex_code)
        return latex_code

    def _extract_text_from_tex(self, tex):
        """Strip LaTeX markup and placeholders to feed clean text to the LLM."""
        # convert = CustomLatexNodes2Text()
        # text = convert.latex_to_text(tex)
        tex = self._process_latex_to_eva(tex)
        text = LatexNodes2Text().latex_to_text(tex)
        text = delete_ph(text)
        return text

    def _merge_with_prev_sections(self, sections: list[dict], idx: int) -> str:
        """
        Merge content of current section with previous two sections (if valid).
        Ignore sections whose 'section' field is "-1" or "0".

        Parameters:
            sections (list of dict): A list of sections, each with keys "section" and "content".
            idx (int): The index of the current section in the list.

        Returns:
            str: The merged content string.
        """
        if not (0 <= idx < len(sections)):
            raise IndexError("Index out of range.")

        merged_content = []
        merged_trans_content = []

        # Check second previous section
        # if idx >= 2:
        #     sec = sections[idx - 2]
        #     if sec["section"] not in {"-1", "0"}:
        #         try:
        #             content = self._extract_text_from_tex(sec["content"])
        #             transed_content = self._extract_text_from_tex(sec["trans_content"])
        #             merged_content.append(content)
        #             merged_trans_content.append(transed_content)
        #         except Exception as e:
        #             pass

        # Check first previous section
        if idx >= 1:
            sec = sections[idx - 1]
            if sec["section"] not in {"-1", "0"}:
                try:
                    content = self._extract_text_from_tex(sec["content"])
                    transed_content = self._extract_text_from_tex(sec["trans_content"])
                    merged_content.append(content)
                    merged_trans_content.append(transed_content)
                except Exception:
                    pass

        # Always include current section
        try:
            content = self._extract_text_from_tex(sections[idx]["content"])
            transed_content = self._extract_text_from_tex(
                sections[idx]["trans_content"]
            )
            merged_content.append(content)
            merged_trans_content.append(transed_content)
        except Exception:
            pass

        return "\n".join(merged_content)

    def build_term_dict(self):
        """Load user-provided or category-derived terminology CSVs."""
        if self.user_term:
            df = pd.read_csv(
                self.user_term,
                header=None,
                names=["English Term", "Chinese Translation"],
            )
            self.term_dict.update(zip(df["English Term"], df["Chinese Translation"]))
        else:
            arxiv_id = os.path.basename(self.project_dir)
            if self.category and self.category.get(arxiv_id):
                term_dict_loaded = False
                for category in self.category[arxiv_id]:
                    file_path = os.path.join("terms", f"{category}.csv")
                    try:
                        df = pd.read_csv(
                            file_path,
                            header=None,
                            names=["English Term", "Chinese Translation"],
                        )
                        self.term_dict.update(
                            zip(df["English Term"], df["Chinese Translation"])
                        )
                        term_dict_loaded = True

                    except FileNotFoundError:
                        continue

                if not term_dict_loaded:
                    try:
                        df = pd.read_csv(
                            "terms/default.csv",
                            header=None,
                            names=["English Term", "Chinese Translation"],
                        )
                        self.term_dict.update(
                            zip(df["English Term"], df["Chinese Translation"])
                        )
                    except FileNotFoundError as e:
                        print(f"Error: Default terminology file not found: {e}")
            else:
                try:
                    df = pd.read_csv(
                        "terms/default.csv",
                        header=None,
                        names=["English Term", "Chinese Translation"],
                    )
                    self.term_dict.update(
                        zip(df["English Term"], df["Chinese Translation"])
                    )
                except FileNotFoundError as e:
                    print(f"Error: Default terminology file not found: {e}")

    def add_placeholder(self):
        """Ensure placeholders appear in the glossary to prevent translation."""
        # Add placeholders from caption, env, input, and newcommand to the vocabulary
        caption_path = os.path.join(self.output_dir, "captions_map.json")
        input_path = os.path.join(self.output_dir, "inputs_map.json")
        env_path = os.path.join(self.output_dir, "envs_map.json")
        command_path = os.path.join(self.output_dir, "newcommands_map.json")

        placeholder_list = []

        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            if "begin" in item:
                placeholder_list.append(item["begin"])
            if "end" in item:
                placeholder_list.append(item["end"])

        with open(env_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            if "placeholder" in item:
                placeholder_list.append(item["placeholder"])

        with open(caption_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            if "placeholder" in item:
                placeholder_list.append(item["placeholder"])

        with open(command_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            if "placeholder" in item:
                placeholder_list.append(item["placeholder"])

        for item in placeholder_list:
            self.term_dict[item] = item
