from typing import Dict, Any, List
from src.agents.tool_agents.base_tool_agent import BaseToolAgent
from pathlib import Path
import sys
import os
import shutil

base_dir = os.getcwd()
sys.path.append(base_dir)

class ReconstructorAgent(BaseToolAgent):
    def __init__(self, 
                 config: Dict[str, Any],
                 project_dir: str = None,
                 output_dir: str = None
                 ):
        super().__init__(agent_name="ReconstructorAgent", config=config)
        self.config = config
        self.project_dir = project_dir  # Project path for parsing
        self.output_dir = output_dir  # Output directory for parsed files

    def execute(self) -> str:
        
        self.log(f"🤖💬 Starting reconstructing for project...⏳: {os.path.basename(self.project_dir)}.")

        from src.formats.latex.reconstruct import LatexConstructor
        sections = self.read_file(Path(self.output_dir, "sections_map.json"), "json")
        captions = self.read_file(Path(self.output_dir, "captions_map.json"), "json")
        envs = self.read_file(Path(self.output_dir, "envs_map.json"), "json")
        newcommands = self.read_file(Path(self.output_dir, "newcommands_map.json"), "json")
        inputs = self.read_file(Path(self.output_dir, "inputs_map.json"), "json")
        transed_latex_dir = self._creat_transed_latex_folder(self.project_dir)
        latex_constructor = LatexConstructor(
                                sections=sections,
                                captions=captions,
                                envs=envs,
                                inputs=inputs,
                                newcommands=newcommands,
                                output_latex_dir=transed_latex_dir
                            )

        latex_constructor.construct()
        self.log(f"✅ Successfully reconstructed {os.path.basename(self.project_dir)}.")
        return transed_latex_dir
            
    def _creat_transed_latex_folder(self, src_dir: str) -> str:
        """
        Create a translated folder by copying the source directory and renaming it.
        """
        if not os.path.isdir(src_dir):
            raise NotADirectoryError(f"The path {src_dir} is not a valid directory.")

        base_name = os.path.basename(src_dir)
        dest_dir = os.path.join(self.output_dir, base_name)

        if os.path.exists(dest_dir):
            shutil.rmtree(dest_dir)
        shutil.copytree(src_dir, dest_dir)

        return dest_dir

# import toml
# import argparse

# parser = argparse.ArgumentParser()
# parser.add_argument("--config", type=str, default="config/default.toml")
# args = parser.parse_args()

# config = toml.load(args.config)
# reconstructor_agent = ReconstructorAgent(config=config,
#                                          project_dir="D:\code\AutoLaTexTrans\data\ICLR/arXiv-2505.16260v1",
#                                          output_dir="D:\code\AutoLaTexTrans\output_merge\ch_arXiv-2505.16260v1")

# reconstructor_agent.execute()