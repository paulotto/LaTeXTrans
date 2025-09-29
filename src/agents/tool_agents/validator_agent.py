"""Validator agent for post-translation LaTeX quality checks."""

from typing import Dict, Any, List, Optional
from src.agents.tool_agents.base_tool_agent import BaseToolAgent

# from base_tool_agent import BaseToolAgent
from pathlib import Path
import sys
import os

from src.formats.latex.validation_utils import (
    extract_command_counts,
    extract_placeholders,
    find_bracket_errors,
    find_reasoning_artifacts,
    sanitize_translated_text,
)

base_dir = os.getcwd()
sys.path.append(base_dir)


class ValidatorAgent(BaseToolAgent):
    """Inspect translated artefacts and report LaTeX-specific issues."""

    def __init__(
        self,
        config: Dict[str, Any],
        project_dir: str,
        output_dir: str,
    ):
        """Initialize validator state and retain workspace paths."""
        super().__init__(agent_name="ValidatorAgent", config=config)
        self.config = config
        self.project_dir = project_dir
        self.output_dir = output_dir

    def execute(
        self, data=None, errors_report: Optional[List[Dict]] = None, **kwargs
    ) -> List[Dict]:
        """Run validation on sections, environments, and captions."""
        self.log(
            f"🤖💬 Start validating for project...⏳: {os.path.basename(self.project_dir)}."
        )
        sections = self.read_file(Path(self.output_dir, "sections_map.json"), "json")
        captions = self.read_file(Path(self.output_dir, "captions_map.json"), "json")
        envs = self.read_file(Path(self.output_dir, "envs_map.json"), "json")

        self._sanitized_any = False
        if errors_report is None:
            parts_need_val = self._extract_parts_need_validate(
                secs=sections,  # secs caps envs
                caps=captions,
                envs=envs,
            )
        else:
            parts_need_val = self._extract_parts_from_report(
                secs=sections, caps=captions, envs=envs, errors_report=errors_report
            )
        errors_report = []
        for part in parts_need_val:
            error_report = self._validate(part)
            if error_report:
                errors_report.append(error_report)

        if self._sanitized_any:
            self.save_file(Path(self.output_dir, "sections_map.json"), "json", sections)
            self.save_file(Path(self.output_dir, "captions_map.json"), "json", captions)
            self.save_file(Path(self.output_dir, "envs_map.json"), "json", envs)
        if errors_report:
            self.save_file(
                Path(self.output_dir, "errors_report.json"), "json", errors_report
            )

        self.log(
            f"✅ Verification Complete for {os.path.basename(self.project_dir)}, remaining Errors: {len(errors_report)}."
        )
        return errors_report

    def _validate(self, part: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Dispatch validation steps for a single document fragment."""
        self._sanitize_part_translation(part)
        command_error = self._validate_command(part)
        ph_error = self._validate_placeholder(part)
        bracket_error = self._validate_closed_brackets(part)
        artifact_error = self._validate_reasoning_artifacts(part)
        error_report = {}

        if (
            not command_error
            and not ph_error
            and not bracket_error
            and not artifact_error
        ):
            return None
        else:
            if "section" in part:
                error_report["part"] = "sec"
                error_report["num_or_ph"] = part["section"]
            elif "env_name" in part:
                error_report["part"] = "env"
                error_report["num_or_ph"] = part["placeholder"]
            elif "cap_type" in part:
                error_report["part"] = "cap"
                error_report["num_or_ph"] = part["placeholder"]

            if command_error:
                error_report["command_error"] = command_error
            if ph_error:
                error_report["ph_error"] = ph_error
            if bracket_error:
                error_report["bracket_error"] = bracket_error
            if artifact_error:
                error_report["artifact_error"] = artifact_error

        return error_report

    def _validate_command(self, part: Dict[str, Any]) -> Optional[str]:
        """Compare LaTeX command usage between source and translation."""
        content = part.get("content", "")
        trans = part.get("trans_content", "")

        src_counter = extract_command_counts(content)
        trans_counter = extract_command_counts(trans)

        if src_counter == trans_counter:
            return None

        errors = []
        for elem, count in src_counter.items():
            trans_count = trans_counter.get(elem, 0)
            if trans_count < count:
                errors.append(f"'{elem}' — expected {count}, found {trans_count}")

        if errors:
            return "LaTeX command translation error or is missing:\n" + "\n".join(
                errors
            )
        return None

    def _validate_placeholder(self, part: Dict[str, Any]) -> Optional[str]:
        """Ensure placeholder tokens are preserved by the translation."""
        original_placeholders = extract_placeholders(part["content"])
        translated_placeholders = extract_placeholders(part["trans_content"])
        missing = original_placeholders - translated_placeholders
        extra = translated_placeholders - original_placeholders
        errors = []
        if missing:
            errors.append(
                f"Missing placeholders: {', '.join(sorted(missing))} translation error or is missing!"
            )
        if extra:
            errors.append(
                f"Extra placeholders: {', '.join(sorted(extra))} translation error or is redundant"
            )
        return "\n".join(errors) if errors else None

    def _validate_closed_brackets(self, part: Dict[str, Any]) -> Optional[str]:
        """Detect bracket mismatches introduced during translation."""
        content = part.get("content", "")
        trans_content = part.get("trans_content", "")
        org_errors = find_bracket_errors(content, include_parentheses=False)
        errors = find_bracket_errors(trans_content)

        if errors and not org_errors:
            return "Brackets error:\n" + "\n".join(errors)
        else:
            return None

    def _validate_reasoning_artifacts(self, part: Dict[str, Any]) -> Optional[str]:
        """Flag reasoning or planning artifacts that slipped through."""

        artifacts = find_reasoning_artifacts(part.get("trans_content", ""))
        if artifacts:
            return "Reasoning artifacts detected:\n" + "\n".join(artifacts)
        return None

    def _sanitize_part_translation(self, part: Dict[str, Any]) -> None:
        """Apply shared sanitization to the translated fragment in-place."""

        original = part.get("trans_content", "")
        sanitized = sanitize_translated_text(original)
        if sanitized != original:
            part["trans_content"] = sanitized
            self._sanitized_any = True
            identifier = (
                part.get("placeholder")
                or part.get("section")
                or part.get("cap_type")
                or "fragment"
            )
            self.log(f"🧹 Sanitized reasoning artifacts for {identifier}.")

    def _extract_parts_need_validate(self, secs, caps, envs):
        """Determine which sections, captions, and environments to validate."""
        secs_need_val = [sec for sec in secs if sec["section"] != 0]
        caps_need_val = caps
        if envs:
            if "need_trans" in envs[0]:
                envs_need_val = [env for env in envs if env["need_trans"]]
            else:
                envs_need_val = [
                    env for env in envs if env["content"] != env["trans_content"]
                ]
        else:
            envs_need_val = []

        return secs_need_val + caps_need_val + envs_need_val

    def _extract_parts_from_report(
        self,
        secs: List[Dict],
        caps: List[Dict],
        envs: List[Dict],
        errors_report: List[Dict],
    ) -> List[Dict]:
        """Resolve original parts referenced in a previous validation report."""
        section_lookup = {s["section"]: s for s in secs}
        caption_lookup = {c["placeholder"]: c for c in caps}
        environment_lookup = {e["placeholder"]: e for e in envs}

        parts_to_validate = []

        for error in errors_report:
            part_type = error.get("part")
            identifier = error.get("num_or_ph")

            if not part_type or not identifier:
                continue

            part = None
            if part_type == "sec":
                part = section_lookup.get(identifier)
            elif part_type == "cap":
                part = caption_lookup.get(identifier)
            elif part_type == "env":
                part = environment_lookup.get(identifier)

            if part:
                parts_to_validate.append(part)

        return parts_to_validate


# import toml
# import argparse
# from tqdm import tqdm
# from src.formats.latex.utils import get_profect_dirs


# parser = argparse.ArgumentParser()
# parser.add_argument("--config", type=str, default="config/default.toml")
# args = parser.parse_args()

# config = toml.load(args.config)
# dir = "D:\code\AutoLaTexTrans\outputs"
# projects = get_profect_dirs(dir)
# for project_dir in tqdm(projects, desc="Processing projects", unit="project"):
#     Validator = ValidatorAgent(config=config,
#                             project_dir=project_dir,
#                             output_dir=project_dir
#                             )
#     errors_report = Validator.execute()
#     if errors_report:
#         for error_report in errors_report:
#             error = ''
#             if "command_error" in error_report:
#                 error += error_report["command_error"] + '\n'
#             if "ph_error" in error_report:
#                 error += error_report["ph_error"] + '\n'
#             if "bracket_error" in error_report:
#                 error += error_report["bracket_error"] + '\n'
#             print(error_report["num_or_ph"])
#             print('\n')
#             print(error)
