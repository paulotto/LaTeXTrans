"""Coordinator agent orchestrating parser, translator, validator, and generator."""

import os
import shutil
from typing import Any, Dict
import sys
import asyncio
from .tool_agents.parser_agent import ParserAgent
from .tool_agents.translator_agent import TranslatorAgent
from .tool_agents.generator_agent import GeneratorAgent
from .tool_agents.validator_agent import ValidatorAgent

base_dir = os.getcwd()
sys.path.append(base_dir)


class CoordinatorAgent:
    """
    The main orchestrator agent for the translation system.
    It coordinates the workflow of various tool agents based on document format
    and configuration.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        project_dir: str,
        output_dir: str,
    ):
        """Persist configuration and derived state required for coordination."""
        self.config = config
        self.name = config.get("sys_name", "LaTeXTrans")
        self.target_language = config.get("target_language", "ch")
        self.source_language = config.get("source_language", "en")
        self.project_dir = project_dir  # Project path for parsing
        self.output_dir = output_dir  # Output directory for parsed files
        self.loop = asyncio.new_event_loop()
        self.mode = config.get("mode", 0)

    def run_async(self, coro):
        """Execute an asynchronous coroutine on the coordinator's event loop."""
        return self.loop.run_until_complete(coro)

    async def workflow_latextrans_async(self) -> None:
        """Run the full translation workflow using asynchronous translator calls."""
        base_name = os.path.basename(self.project_dir)
        transed_project_dir = os.path.join(
            self.output_dir, f"{self.target_language}_{base_name}"
        )

        os.makedirs(transed_project_dir, exist_ok=True)

        parser_agent = ParserAgent(
            config=self.config,
            project_dir=self.project_dir,
            output_dir=transed_project_dir,
        )
        parser_agent.execute()

        translator_agent = TranslatorAgent(
            config=self.config,
            project_dir=self.project_dir,
            output_dir=transed_project_dir,
            trans_mode=self.mode,
        )
        await translator_agent.execute()  # await

        if self.config.get("enable_validator", True):
            validator_agent = ValidatorAgent(
                config=self.config,
                project_dir=self.project_dir,
                output_dir=transed_project_dir,
            )

            errors_report = validator_agent.execute()
            max_retries = int(self.config.get("validator_max_retries", 2))
            retry_count = 0

            while errors_report and retry_count < max_retries:
                translator_agent.trans_mode = 1
                translator_agent.errors_report = errors_report
                await translator_agent.execute(
                    error_retry_count=retry_count,
                    Maxtry=max_retries,
                )

                retry_count += 1
                errors_report = validator_agent.execute(errors_report=errors_report)

            if errors_report:
                validator_agent.log(
                    "⚠️ Validation still reports issues after maximum retries.",
                    level="warning",
                )

        generator_agent = GeneratorAgent(
            config=self.config,
            project_dir=self.project_dir,
            output_dir=transed_project_dir,
        )
        try:
            PDF_file_path = generator_agent.execute()
        except Exception as e:
            print(
                f"🤖🚧 {self.name}: Failed to translated {os.path.basename(self.project_dir)}.{e}"
            )
            return

        if PDF_file_path:
            new_PDF_path = os.path.join(
                transed_project_dir, f"{self.target_language}_{base_name}.pdf"
            )
            shutil.move(PDF_file_path, new_PDF_path)
            print(
                f"🤖🎉 {self.name}: Successfully translated {os.path.basename(self.project_dir)} to {new_PDF_path}."
            )
        else:
            print(
                f"🤖🚧 {self.name}: Failed to translated {os.path.basename(self.project_dir)}."
            )

    def workflow_latextrans(self) -> None:
        """Convenience wrapper to launch the async workflow with loop management."""

        if hasattr(self, "loop") and not self.loop.is_closed():
            self.loop.close()

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            self.loop.run_until_complete(self.workflow_latextrans_async())

        finally:
            # Complete all asynchronous resource recycling
            if tasks := asyncio.all_tasks(self.loop):
                self.loop.run_until_complete(
                    asyncio.gather(*tasks, return_exceptions=True)
                )

            # Special handling of asynchronous I/O recycling in Windows
            if sys.platform == "win32":
                self.loop.run_until_complete(self.loop.shutdown_asyncgens())

            self.loop.run_until_complete(self.loop.shutdown_default_executor())
