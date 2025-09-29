"""Shared helpers for validating LaTeX translations."""

from __future__ import annotations

from collections import Counter
import re
from typing import Iterable, List, Set

from pylatexenc.latexwalker import LatexWalker

# Commands that commonly appear as plain text and should be ignored when counting
IGNORED_COMMANDS: Set[str] = {"eg", "ie"}

_THINK_TOKEN_RE = re.compile(r"</?think>", re.IGNORECASE)
_THINK_BLOCK_RE = re.compile(r"<think>.*?(?:</think>|$)", re.IGNORECASE | re.DOTALL)

_REASONING_LINE_PATTERNS = (
    re.compile(r"^%\s*(translation|reasoning|note)\b.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*(?:Reasoning|Thought|Note|Notes|Translation)\s*:\s.*$", re.IGNORECASE | re.MULTILINE),
)

_INSTRUCTION_SENTENCE_PATTERNS = (
    re.compile(
        r"\s*(?:the\s+)?assistant\s+should[^.!?\n]*(?:[.!?](?=\s|$)|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\s*(?:please\s+)?(?:make|ensure|confirm)\s+that\s+the\s+latex\s+command[^.!?\n]*(?:[.!?](?=\s|$)|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\s*correct\s+the\s+translation[^.!?\n]*(?:[.!?](?=\s|$)|$)",
        re.IGNORECASE,
    ),
)

_PLACEHOLDER_PATTERNS = (
    re.compile(r"<PLACEHOLDER_[^>]+?_begin>", re.IGNORECASE),
    re.compile(r"<PLACEHOLDER_[^>]+?_end>", re.IGNORECASE),
    re.compile(r"<PLACEHOLDER_CAP_\d+>", re.IGNORECASE),
    re.compile(r"<PLACEHOLDER_ENV_\d+>", re.IGNORECASE),
)


def extract_placeholders(content: str) -> Set[str]:
    """Return all placeholder tokens present in *content*."""

    placeholders: Set[str] = set()
    for pattern in _PLACEHOLDER_PATTERNS:
        placeholders.update(pattern.findall(content))
    return placeholders


def extract_command_counts(latex_code: str) -> Counter:
    """Return counts for each LaTeX macro/environment within *latex_code*."""

    walker = LatexWalker(latex_code)
    nodes, _, _ = walker.get_latex_nodes()
    counter: Counter = Counter()

    def recurse(node_iterable: Iterable) -> None:
        for node in node_iterable:
            clsname = node.__class__.__name__

            if clsname == "LatexMacroNode":
                macro_name = node.macroname

                if macro_name in IGNORED_COMMANDS:
                    continue
                if len(macro_name) == 1 and not macro_name.isalpha():
                    continue

                counter[f"\\{macro_name}"] += 1

                if node.nodeargd:
                    for arg in node.nodeargd.argnlist:
                        if arg is not None:
                            recurse([arg])

            elif clsname == "LatexEnvironmentNode":
                env_name = node.environmentname
                counter[f"\\begin{{{env_name}}}"] += 1
                recurse(node.nodelist)
                counter[f"\\end{{{env_name}}}"] += 1

            elif hasattr(node, "nodelist") and node.nodelist:
                recurse(node.nodelist)

    recurse(nodes)
    return counter


def find_bracket_errors(content: str, include_parentheses: bool = True) -> List[str]:
    """Identify bracket mismatches within *content*.

    Parameters
    ----------
    include_parentheses:
        When ``False`` only ``[]`` and ``{}`` are considered. Useful when
        comparing against the original LaTeX where parentheses might be
        intentionally unbalanced.
    """

    if include_parentheses:
        bracket_pairs = {"(": ")", "[": "]", "{": "}"}
    else:
        bracket_pairs = {"[": "]", "{": "}"}

    opening = set(bracket_pairs)
    closing = set(bracket_pairs.values())

    stack: List[tuple[str, int]] = []
    errors: List[str] = []

    for idx, char in enumerate(content):
        if char in opening:
            stack.append((char, idx))
        elif char in closing:
            if not stack:
                fragment = content[max(0, idx - 10) : idx + 10]
                errors.append(
                    f"Extra closing bracket '{char}' at position {idx}, context: {fragment}"
                )
            else:
                last_open, open_idx = stack.pop()
                if bracket_pairs[last_open] != char:
                    fragment = content[open_idx : idx + 1]
                    errors.append(
                        f"Bracket mismatch: '{last_open}' opened at {open_idx} does not match '{char}' at {idx}, fragment: {fragment}"
                    )

    for open_bracket, pos in stack:
        fragment = content[pos : pos + 20]
        errors.append(
            f"Unmatched opening bracket '{open_bracket}' at position {pos}, fragment: {fragment}"
        )

    return errors


def find_reasoning_artifacts(text: str) -> List[str]:
    """Detect reasoning artifacts such as ``<think>`` blocks or diagnostic notes."""

    artifacts: List[str] = []

    if _THINK_BLOCK_RE.search(text):
        artifacts.append("Found <think> blocks left in the output.")
    if _THINK_TOKEN_RE.search(text):
        artifacts.append("Found <think> tags left in the output.")

    for pattern in _REASONING_LINE_PATTERNS:
        if pattern.search(text):
            artifacts.append("Detected reasoning commentary lines that should be removed.")
            break

    return artifacts


def has_reasoning_artifacts(text: str) -> bool:
    """Return ``True`` if *text* contains any reasoning artifacts."""

    return bool(find_reasoning_artifacts(text))


def sanitize_translated_text(text: str) -> str:
    """Remove reasoning artifacts and leading chatter before LaTeX commands."""

    if not text:
        return ""

    cleaned = _THINK_BLOCK_RE.sub("", text)
    cleaned = _THINK_TOKEN_RE.sub("", cleaned)

    for pattern in _REASONING_LINE_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    for pattern in _INSTRUCTION_SENTENCE_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    cleaned = cleaned.strip()

    first_backslash = cleaned.find("\\")
    if first_backslash > 0:
        cleaned = cleaned[first_backslash:]

    cleaned = cleaned.lstrip()

    cleaned = re.sub(r"\n{2,}", "\n", cleaned)
    return cleaned.strip()