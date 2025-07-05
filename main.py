import toml
import argparse
import os
import sys
from src.agents.coordinator_agent import CoordinatorAgent
from src.formats.latex.utils import get_profect_dirs, batch_download_arxiv_tex, extract_compressed_files
from tqdm import tqdm

base_dir = os.getcwd()
sys.path.append(base_dir)

def main():
    """
    Main function to run the TexTrans application.
    It initializes the CoordinatorAgent and starts the workflow based on the document format.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="config/default.toml")
    args = parser.parse_args()
    config = toml.load(args.config)
    paper_list = config["paper_list"]
    projects_dir = os.path.join(base_dir, config["tex_sources_dir"]) if config["tex_sources_dir"] else os.path.join(base_dir, "tex_sources")
    output_dir = os.path.join(base_dir, config["output_dir"]) if config["output_dir"] else os.path.join(base_dir, "output")

    if paper_list:
        projects = batch_download_arxiv_tex(paper_list, projects_dir)
        extract_compressed_files(projects_dir)
    else:
        print("⚠️ No paper list provided. Using existing projects in the specified directory.")
        extract_compressed_files(projects_dir)
        projects = get_profect_dirs(projects_dir)
        if not projects:
            raise ValueError("❌ No projects found in the specified directory. Please check the 'tex_sources_dir' and 'paper list' in the config file.")

    for project_dir in tqdm(projects[0:50], desc="Processing projects", unit="project"):

        try:
            LaTexTrans = CoordinatorAgent(config=config, 
                                        project_dir=project_dir,
                                        output_dir=output_dir
                                        )

            LaTexTrans.workflow_latextrans()

        except Exception as e:
            print(f"❌ Error processing project {os.path.basename(project_dir)}: {e}")
            continue
            
    
if __name__ == "__main__":
    main()
