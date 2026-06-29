"""PatchAgent — generates minimal code fixes for critical findings using an LLM."""

from __future__ import annotations

import ast
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

PATCH_PROMPT = """\
You are an expert software engineer performing a targeted code fix.

## Context
The following is the relevant code extracted from a pull-request diff (added lines only):

```
{original_code}
```

## Issue to Fix
**Message:** {issue_message}
**Suggestion:** {issue_suggestion}

## Instructions
- Produce the minimal corrected version of the code above that resolves this specific issue.
- Do NOT add explanations, comments about the fix, markdown fences, \
or any text other than the fixed code.
- Preserve the original indentation and surrounding structure.
- Output ONLY the fixed code, nothing else.
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n?|^```$", re.MULTILINE)


def _strip_markdown_fences(text: str) -> str:
    """Remove leading/trailing markdown code fences the LLM may add anyway."""
    return _FENCE_RE.sub("", text).strip()


def _extract_added_lines(diff: str) -> str:
    """Return only the added lines from the diff as plain source code."""
    lines = []
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
    return "\n".join(lines)


def _is_valid_python(code: str) -> bool:
    """Return True if *code* parses without a SyntaxError."""
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _coerce_llm_text(response: Any) -> str:
    """Extract plain text from a LangChain LLM response object."""
    if hasattr(response, "content"):
        content = response.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    parts.append(str(block.get("text", "")))
                else:
                    parts.append(str(block))
            return "".join(parts)
    return str(response)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class PatchAgent:
    """Generates minimal code patches for a single critical finding.

    The agent is intentionally stateless — create one instance per call or
    reuse across calls; it holds no mutable state.
    """

    def generate_patch(self, diff: str, issue: dict, llm: Any) -> dict:
        """Generate a minimal fix for *issue* found in *diff*.

        Parameters
        ----------
        diff:
            Raw unified diff string (e.g. from ``git diff``).
        issue:
            A finding dict with at least ``message``, ``suggestion``, and
            optionally ``id`` keys.
        llm:
            Any LangChain LLM / chat model instance.

        Returns
        -------
        dict
            On success::

                {
                    "success": True,
                    "patch": "<fixed source code>",
                    "issue_id": <issue id or None>,
                }

            On failure::

                {
                    "success": False,
                    "error": "<reason>",
                    "issue_id": <issue id or None>,
                }
        """
        issue_id = issue.get("id")
        issue_message = issue.get("message", "")
        issue_suggestion = issue.get("suggestion", "")

        if not diff or not diff.strip():
            logger.warning("PatchAgent.generate_patch: empty diff received.")
            return {
                "success": False,
                "error": "empty diff",
                "issue_id": issue_id,
            }

        # 1. Extract added lines — these are the lines the LLM should fix
        original_code = _extract_added_lines(diff)
        if not original_code.strip():
            return {
                "success": False,
                "error": "no added lines found in diff",
                "issue_id": issue_id,
            }

        # 2. Build prompt
        prompt = PATCH_PROMPT.format(
            original_code=original_code,
            issue_message=issue_message,
            issue_suggestion=issue_suggestion,
        )

        # 3. Call LLM (plain string output — no JSON parsing needed)
        logger.info(
            "PatchAgent: invoking LLM for issue_id=%s message=%r",
            issue_id,
            issue_message[:80],
        )
        try:
            response = llm.invoke(prompt)
            raw_text = _coerce_llm_text(response)
        except Exception as exc:
            logger.exception("PatchAgent: LLM call failed: %s", exc)
            return {
                "success": False,
                "error": f"LLM call failed: {exc}",
                "issue_id": issue_id,
            }

        # 4. Clean up any stray markdown fences
        fixed_code = _strip_markdown_fences(raw_text)

        if not fixed_code:
            return {
                "success": False,
                "error": "LLM returned empty response",
                "issue_id": issue_id,
            }

        # 5. Validate syntax (Python only; non-Python diffs pass through)
        if not _is_valid_python(fixed_code):
            logger.warning(
                "PatchAgent: LLM patch failed syntax check for issue_id=%s", issue_id
            )
            return {
                "success": False,
                "error": "invalid syntax",
                "issue_id": issue_id,
            }

        logger.info(
            "PatchAgent: patch generated successfully for issue_id=%s (%d chars)",
            issue_id,
            len(fixed_code),
        )
        return {
            "success": True,
            "patch": fixed_code,
            "issue_id": issue_id,
        }
