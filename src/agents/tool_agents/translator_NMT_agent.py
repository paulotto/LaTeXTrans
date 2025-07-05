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

class TranslatorAgent_NMT(BaseToolAgent):
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
        captions = self.read_file(Path(self.output_dir, "captions_map.json"), "json")
        envs = self.read_file(Path(self.output_dir, "envs_map.json"), "json")
        
        if self.trans_mode == 0 or self.trans_mode == 2:
            self.log(f"🤖💬 Starting translating for project...⏳: {os.path.basename(self.project_dir)}.")
            with ThreadPoolExecutor(max_workers=3) as executor:

                futures = [executor.submit(lambda i, sec: (i, self.translate(sec)), i, sec) 
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
                  section: Dict[str, Any],
                  ) -> Dict[str, Any]:
        """
        Translates the input data.
        translate section then envs and captions in this section
        """

        # if section["section"] != "0" and section["section"] != "-1":
        #     section = self._translate_section(section) # LaTexTrans
        section = self._translate_section(section) # baseline

        return section



    def _translate_section(self, section: Dict[str, Any], error_message=None) -> Dict[str, Any]:
        """
        Translates the sections of the input data.
        """
        transed_section = section.copy()
        if self.trans_mode == 0:
            try:
                transed_section["trans_content"] = self._request_google_api( 
                                                            section["content"]
                                                            )
            except Exception as e:
                print(e)
                transed_section["trans_content"] = section["content"]

        return transed_section

    def _request_niutrans_api(self, source_text: str,):
        import requests
        import time
        import hashlib
        import json

        apiUrl = "https://api.niutrans.com"
        transUrl = apiUrl + "/v2/text/translate"  # 上传并翻译接口 

        from_language = "ja"
        to_language = self.target_language  
        app_id = "yV71751099588039"  # 应用唯一标识，在'控制台->API应用'中查看
        apikey = "80667f1ee2480c5cd4e380fda5ceb341"  # 在'控制台->API应用'中查看
        src_text = source_text

        # 生成权限字符串
        def generate_auth_str(params):
            sorted_params = sorted(list(params.items()) + [('apikey', apikey)], key=lambda x: x[0])
            param_str = '&'.join([f'{key}={value}' for key, value in sorted_params])
            md5 = hashlib.md5()
            md5.update(param_str.encode('utf-8'))
            auth_str = md5.hexdigest()
            return auth_str

        # 获取翻译结果
        def translate():
            data = {
                'from': from_language,
                'to': to_language,
                'appId': app_id,
                'timestamp': int(time.time()),
                'srcText': src_text
            }

            auth_str = generate_auth_str(data)
            data['authStr'] = auth_str
            response = requests.post(transUrl, data=data)
            # print("翻译结果："+str(response.json()))
            return response.json()["tgtText"].strip()

        tgtText = translate()
        return tgtText


    def _request_google_api(self, source_text: str):
        """
        Requests the Google Translate API to translate the source text.
        """
        import requests
        import json

        base_url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "en",   # 源语言
            "tl": "ja",   # 目标语言（韩语）
            "dt": "t",
            "q": source_text,
        }

        try:

            response = requests.get(base_url, params=params)
            result = response.json()
        
        # 打印原始返回内容
        # print("".join([item[0] for item in result[0]]) )
        
            return "".join([item[0] for item in result[0]])
        except Exception as e:
            print(f"解析翻译失败: {e}")
            return source_text

# import toml
# import argparse

# parser = argparse.ArgumentParser()
# parser.add_argument("--config", type=str, default="config/default.toml")
# args = parser.parse_args()

# config = toml.load(args.config)

# trans_agent = TranslatorAgent(config)
# trans_agent.execute()

