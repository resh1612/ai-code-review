"""Code quality analysis agent using tree-sitter for AST parsing and LangChain for LLM inference."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

logger = logging.getLogger(__name__)

JSON_RETRY_MESSAGE = (
    "Your previous response was not valid JSON. Return ONLY a JSON array, nothing else."
)

# ---------------------------------------------------------------------------
# Prompt constant
# ---------------------------------------------------------------------------

CODE_QUALITY_PROMPT = """\
You are a senior software engineer conducting a code review.

Analyse the following pull-request diff and the AST summary extracted from the \
added lines.

## Diff
```
{diff}
```

## AST Summary (added Python code)
{ast_summary}

## Instructions
- Report ONLY real issues: concrete bugs, security risks, correctness problems, \
and meaningful complexity or duplication concerns.
- Do NOT report style preferences, formatting nitpicks, or subjective opinions \
unless they indicate a real problem.
- If there are no issues, return an empty array [].

Return ONLY a valid JSON array with no extra fields. Each element must match \
this schema exactly:
[{{"line_number": int or null, "severity": "critical"|"warning"|"info", \
"category": "security"|"complexity"|"naming"|"duplication"|"style"|"bug", \
"message": "what the problem is", "suggestion": "how to fix it"}}]

Do not include markdown formatting in your JSON response.
"""

# ---------------------------------------------------------------------------
# AST helpers (tree-sitter)
# ---------------------------------------------------------------------------

_FUNCTION_DEF_TYPES = {"function_definition", "async_function_definition"}


def _get_node_text(node: Any, source: bytes) -> str:
    """Extract UTF-8 text for a tree-sitter node from the raw source bytes."""
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _collect_functions(node: Any, source: bytes) -> list[dict]:
    """Recursively walk the tree and collect function metadata."""
    results: list[dict] = []

    if node.type in _FUNCTION_DEF_TYPES:
        # The first named child of a function_definition is the 'name' identifier
        name_node = node.child_by_field_name("name")
        func_name = _get_node_text(name_node, source) if name_node else "<anonymous>"

        start_line = node.start_point[0] + 1  # tree-sitter is 0-indexed
        end_line = node.end_point[0] + 1
        line_count = end_line - start_line + 1

        results.append(
            {
                "name": func_name,
                "start_line": start_line,
                "end_line": end_line,
                "line_count": line_count,
                "complexity_warning": line_count > 20,
            }
        )

    for child in node.children:
        results.extend(_collect_functions(child, source))

    return results


def _parse_python_ast(added_code: str) -> list[dict]:
    """Parse *added_code* with tree-sitter and return function metadata."""
    try:
        import tree_sitter_python as tspython  # type: ignore[import]
        from tree_sitter import Language, Parser  # type: ignore[import]
    except ImportError as exc:
        logger.warning("tree-sitter or tree-sitter-python not installed: %s", exc)
        return []

    py_language = Language(tspython.language())
    parser = Parser(py_language)

    source_bytes = added_code.encode("utf-8")
    tree = parser.parse(source_bytes)
    return _collect_functions(tree.root_node, source_bytes)


def _build_ast_summary(functions: list[dict]) -> str:
    """Render function metadata as a human-readable block for the prompt."""
    if not functions:
        return "No function definitions detected in the added lines."

    lines: list[str] = []
    for fn in functions:
        warning = " ⚠ EXCEEDS 20 LINES" if fn["complexity_warning"] else ""
        lines.append(
            f"  - {fn['name']}(): lines {fn['start_line']}–{fn['end_line']} "
            f"({fn['line_count']} lines){warning}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Diff helpers
# ---------------------------------------------------------------------------


def _extract_added_lines(diff: str) -> str:
    """Return only the lines added by the diff (starting with '+', excluding '+++')."""
    added: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            # Strip the leading '+' to get plain source code
            added.append(line[1:])
    return "\n".join(added)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class CodeQualityAgent:
    """Analyses a git diff for code quality issues using tree-sitter + an LLM.

    Parameters
    ----------
    llm:
        Any LangChain chat/LLM instance (e.g. ``ChatGoogleGenerativeAI``).
    """

    def __init__(self, llm: Any) -> None:
        self.llm = llm
        self._parser = JsonOutputParser()
        self._prompt = PromptTemplate(
            template=CODE_QUALITY_PROMPT,
            input_variables=["diff", "ast_summary"],
        )

    @staticmethod
    def _coerce_response_text(response: Any) -> str:
        """Normalise LangChain LLM responses to plain text for JSON parsing."""
        if hasattr(response, "content"):
            content = response.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts: list[str] = []
                for block in content:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict):
                        parts.append(str(block.get("text", "")))
                    else:
                        parts.append(str(block))
                return "".join(parts)
        return str(response)

    def _parse_llm_json(self, content: str) -> list[dict]:
        """Parse LLM output as JSON, surfacing JSONDecodeError for retry handling."""
        try:
            parsed = self._parser.parse(content)
        except OutputParserException as exc:
            if isinstance(exc.__cause__, json.JSONDecodeError):
                raise exc.__cause__ from exc
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as decode_exc:
                raise decode_exc from exc
        except json.JSONDecodeError:
            raise

        if not isinstance(parsed, list):
            raise json.JSONDecodeError("Expected a JSON array.", content, 0)

        return parsed

    def _invoke_with_json_retry(self, inputs: dict) -> list[dict]:
        """Call the LLM and parse JSON, retrying up to 2 times on decode failure."""
        prompt_text = self._prompt.format(**inputs)
        current_prompt = prompt_text
        max_retries = 2

        for attempt in range(max_retries + 1):
            response = self.llm.invoke(current_prompt)
            content = self._coerce_response_text(response)

            try:
                return self._parse_llm_json(content)
            except json.JSONDecodeError:
                if attempt >= max_retries:
                    raise
                logger.warning(
                    "LLM returned invalid JSON on attempt %d/%d; retrying.",
                    attempt + 1,
                    max_retries + 1,
                )
                current_prompt = (
                    f"{prompt_text}\n\n"
                    f"Your previous response was:\n{content}\n\n"
                    f"{JSON_RETRY_MESSAGE}"
                )

        return []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, diff: str, language: str = "python") -> list[dict]:
        """Analyse *diff* and return a list of code-quality issue dicts.

        Parameters
        ----------
        diff:
            Raw unified diff string (e.g. from ``git diff``).
        language:
            Source language. Only ``"python"`` triggers tree-sitter AST
            analysis; other languages skip AST extraction but still run
            the LLM review.

        Returns
        -------
        list[dict]
            Each dict has keys: ``line_number``, ``severity``, ``category``,
            ``message``, ``suggestion``.
        """
        if not diff or not diff.strip():
            logger.info("Empty diff received; returning no issues.")
            return []

        # 1. Extract added lines from the diff
        added_code = _extract_added_lines(diff)

        # 2. AST analysis (Python only)
        functions: list[dict] = []
        if language.lower() == "python" and added_code.strip():
            functions = _parse_python_ast(added_code)
            logger.debug("Extracted %d function(s) from diff AST.", len(functions))

        ast_summary = _build_ast_summary(functions)

        # 3. Build prompt and call LLM via LangChain chain
        logger.info("Invoking LLM for code quality analysis (language=%s).", language)
        try:
            issues: list[dict] = self._invoke_with_json_retry(
                {"diff": diff, "ast_summary": ast_summary}
            )
        except Exception as exc:
            logger.exception("LLM invocation failed: %s", exc)
            raise

        # 4. Normalise and validate each issue dict
        normalised: list[dict] = []
        valid_severities = {"critical", "warning", "info"}
        valid_categories = {
            "security",
            "complexity",
            "naming",
            "duplication",
            "style",
            "bug",
        }

        for raw in issues if isinstance(issues, list) else []:
            if not isinstance(raw, dict):
                continue

            issue: dict = {
                "line_number": raw.get("line_number"),  # int or None
                "severity": raw.get("severity", "info"),
                "category": raw.get("category", "style"),
                "message": str(raw.get("message", "")),
                "suggestion": str(raw.get("suggestion", "")),
            }

            # Coerce unknown severity/category to safe defaults
            if issue["severity"] not in valid_severities:
                issue["severity"] = "info"
            if issue["category"] not in valid_categories:
                issue["category"] = "style"

            # Ensure line_number is int or None
            ln = issue["line_number"]
            if ln is not None:
                try:
                    issue["line_number"] = int(ln)
                except (TypeError, ValueError):
                    issue["line_number"] = None

            normalised.append(issue)

        logger.info("Analysis complete: %d issue(s) found.", len(normalised))
        return normalised
