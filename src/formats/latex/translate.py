from typing import List, Dict, Any
from .prompts import *
import requests
import time
import re

class LatexTranslator:
    def __init__(self, 
                 sections: List[Dict[str, Any]], 
                 captions: List[Dict[str, Any]], 
                 envs: List[Dict[str, Any]],
                 model: str,
                 API_KEY: str,
                 API_URL: str,
                 target_language: str = "ch",
                 ):
        self.sections = sections
        self.captions = captions
        self.envs = envs
        self.model = model
        self.target_language = target_language
        self.API_KEY = API_KEY
        self.API_URL = API_URL

    def translate(self, section: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translates the input data.
        translate section then envs and captions in this section
        """
        placeholder_pattern_cap= r"<PLACEHOLDER_CAP_\d+>"
        placeholder_pattern_env= r"<PLACEHOLDER_ENV_\d+>"
        placeholders_cap = re.findall(placeholder_pattern_cap, section["content"])
        placeholders_env = re.findall(placeholder_pattern_env, section["content"])

        for placeholder in placeholders_env:
            need_trans = True
            for i, env in enumerate(self.envs):
                if placeholder == env["placeholder"]:
                    placeholders_cap_in_env = re.findall(placeholder_pattern_cap, env["content"])
                    placeholders_cap.extend(placeholders_cap_in_env)
                    if placeholders_cap_in_env: # have captions,do not trans
                        need_trans = False

                    self.envs[i] = self._translate_env(env, need_trans)
                    break

        placeholders_cap = list(dict.fromkeys(placeholders_cap))  # remove duplicates

        for placeholder in placeholders_cap:
            for i, caption in enumerate(self.captions):
                if placeholder == caption["placeholder"]:
                    self.captions[i] = self._translate_caption(caption)
                    break

        if section["section"] != 0:
            section = self._translate_section(section)

        return section

    def _translate_section(self, section: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translates the sections of the input data.
        """
        transed_section = section.copy()
        section_num = section["section"]
        transed_section["trans_content"] = self._request_llm(section_system_prompt, 
                                                     section["content"], 
                                                     fail_part = f"section {section_num}"
                                                     )

        return transed_section

    def _translate_caption(self, caption: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translates the captions of the input data.
        """
        transed_caption = caption.copy()
        placeholder = caption["placeholder"]
        transed_caption["trans_content"] = self._request_llm(caption_system_prompt, 
                                                     caption["content"], 
                                                     fail_part = f"caption {placeholder}"
                                                     )

        return transed_caption

    def _translate_env(self, env: Dict[str, Any], need_trans: bool = True) -> Dict[str, Any]:
        """
        Translates an environment block (env) based on whether translation is needed.
        """
        transed_env = env.copy()
        no_translate_envs = [
                             'equation', 'align', 'align*', 'gather', 'gather*', 'verbatim', 'verbatim*', 'lstlisting*', 'minted', 'minted*',
                             'equation*', 'alignat', 'alignat*', 'flalign', 'flalign*', 'split', 'split*', 'cases', 'cases*', 'subequations', 
                             'figure', 'figure*', 'wrapfigure', 'SCfigure', 'tikzpicture', 'CJK', 'scope',
                             'tabularx', 'tabulary', 'longtable*', 'sidewaystable', 'table', 'table*', 'tabular', 'tabular*', 'longtable',
                             'multline', 'multline*', 'lstlisting', 'tcolorbox', 'thebibliography', 'bibliography', 'bibitem',
                             'algorithm', 'algorithmic', 'algorithmicx', 'algorithm2e', 'algorithmicx*', 'algorithmic*', 'algorithm*'
                             ]
        placeholder = env["placeholder"]
        if need_trans:
            if env["env_name"] in no_translate_envs:
                transed_env["trans_content"] = env["content"]
            else:
                transed_env["trans_content"] = self._request_llm(env_system_prompt, 
                                                         env["content"], 
                                                         fail_part = f"env {placeholder}"
                                                         )
        else:
            transed_env["trans_content"] = env["content"]

        return transed_env
                    
    def _request_llm(self, system_prompt: str, text: str, fail_part: str) -> str:

        payload = {
            "model": f"{self.model}",
            "messages": [
                {
                    "role": "system", 
                    "content": f"{system_prompt}"
                },
                {
                    "role": "user", 
                    "content": f"{text}"
                }
            ],
            "temperature": 0.7,
            # "max_length": 100000,
            "max_new_tokens": 8192
        }

        headers = {
            "Authorization": f"Bearer {self.API_KEY}",
            "Content-Type": "application/json"
        }
        
        
        for attempt in range(1, 4):
            try:
                response = requests.post(self.API_URL, json=payload, headers=headers, timeout=100)
                response.raise_for_status()  
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            except requests.exceptions.RequestException as e:
                print(f"⚠️ The {attempt}th request to translate {fail_part} failed: {e}")
                if attempt < 3:
                    time.sleep(3)  
                else:
                    print(f"❌ Failed to translate text, return the original text:{fail_part}.")
                    return text  

        
