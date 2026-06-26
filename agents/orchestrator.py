"""LangGraph orchestrator for AI-powered pull-request review.

Graph topology:
    START → planner_node → [code_quality_node, security_node] → aggregator_node → END

code_quality_node and security_node run in parallel after planner_node completes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import operator
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from agents.code_quality_agent import CodeQualityAgent
from core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------


class PRReviewState(TypedDict):
    """Shared state passed between all LangGraph nodes."""

    pr_diff: str
    repo_name: str
    pr_number: int
    language: str
    code_quality_findings: list[dict]
    security_findings: list[dict]
    test_findings: list[dict]
    final_summary: str
    error: str | None
    agent_traces: Annotated[list[dict], operator.add]


# ---------------------------------------------------------------------------
# Tracing + node wrapper
# ---------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _trace_entry(agent: str, started_at: datetime, status: str) -> dict:
    return {
        "agent": agent,
        "started_at": started_at.isoformat(),
        "status": status,
    }


def _run_traced_node(
    node_name: str,
    state: PRReviewState,
    handler: Callable[[PRReviewState], dict],
) -> dict:
    """Execute a node handler with tracing and uniform error handling."""
    started_at = _utc_now()
    traces = [_trace_entry(node_name, started_at, "running")]

    try:
        result = handler(state)
        traces.append(_trace_entry(node_name, started_at, "completed"))
        return {**result, "agent_traces": traces}
    except Exception as exc:
        logger.exception("%s failed: %s", node_name, exc)
        traces.append(_trace_entry(node_name, started_at, "failed"))
        return {
            "agent_traces": traces,
            "error": f"{node_name} failed: {str(exc)}",
        }


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

# Map file extension → canonical language name
_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".rs": "rust",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".cs": "csharp",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
}

# Regex that matches diff hunk headers like:
#   +++ b/path/to/file.py
_DIFF_FILE_HEADER_RE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


def _detect_language(diff: str) -> str:
    """Infer the primary language from file extensions found in the diff headers."""
    matches = _DIFF_FILE_HEADER_RE.findall(diff)
    freq: dict[str, int] = {}
    for path in matches:
        ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
        lang = _EXT_TO_LANG.get(ext)
        if lang:
            freq[lang] = freq.get(lang, 0) + 1

    if not freq:
        return "python"  # safe default

    return max(freq, key=lambda k: freq[k])


# ---------------------------------------------------------------------------
# Security scanner
# ---------------------------------------------------------------------------

# (pattern, message, suggestion) triples for static regex checks
_SECURITY_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(
            r'(?:password|passwd|secret|api_?key|auth_?token)\s*=\s*["\'][^"\']{4,}["\']',
            re.IGNORECASE,
        ),
        "Possible hardcoded credential detected.",
        "Store secrets in environment variables or a secrets manager, never in source code.",
    ),
    (
        re.compile(
            r'(?:api_?key|token|secret)\s*=\s*["\'][A-Za-z0-9+/]{16,}["\']',
            re.IGNORECASE,
        ),
        "Possible hardcoded API key or token detected.",
        "Move this value to an environment variable and load it at runtime.",
    ),
    (
        re.compile(
            r'(?:SELECT|INSERT|UPDATE|DELETE)\b.{0,60}\+\s*\w',
            re.IGNORECASE,
        ),
        "SQL query constructed via string concatenation — potential SQL injection.",
        "Use parameterised queries or an ORM instead of string concatenation.",
    ),
    (
        re.compile(r'\beval\s*\(', re.IGNORECASE),
        "Use of eval() is dangerous and can execute arbitrary code.",
        "Replace eval() with a safe alternative such as ast.literal_eval() or JSON parsing.",
    ),
]

_SECURITY_PROMPT = """\
You are a security-focused code reviewer. You have been given a diff and a list \
of potential security issues flagged by static analysis.

## Diff
```
{diff}
```

## Preliminary Static Findings
{static_findings}

## Task
Review each static finding in context and confirm whether it is a genuine \
security risk. Add any additional security issues you spot that the regex scanner \
may have missed (e.g. path traversal, deserialization issues, SSRF, XXE).

Return ONLY a valid JSON array — no markdown code blocks. Each element must have:
- "line_number": integer or null
- "severity": "critical" | "warning" | "info"
- "category": "security"
- "message": string
- "suggestion": string

If there are no security issues at all, return [].
"""


def _scan_security_patterns(diff: str) -> list[dict]:
    """Run regex-based static security checks over added lines in the diff."""
    findings: list[dict] = []
    for i, line in enumerate(diff.splitlines(), start=1):
        if not line.startswith("+") or line.startswith("+++"):
            continue
        content = line[1:]
        for pattern, message, suggestion in _SECURITY_PATTERNS:
            if pattern.search(content):
                findings.append(
                    {
                        "line_number": i,
                        "severity": "critical",
                        "category": "security",
                        "message": message,
                        "suggestion": suggestion,
                    }
                )
    return findings


# ---------------------------------------------------------------------------
# LLM factory (module-level singleton, lazy)
# ---------------------------------------------------------------------------

_llm: ChatGoogleGenerativeAI | None = None


def _get_llm() -> ChatGoogleGenerativeAI:
    global _llm
    if _llm is None:
        _llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0,
        )
    return _llm


# ---------------------------------------------------------------------------
# Aggregator helpers
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
_SEVERITY_EMOJI = {"critical": "🔴", "warning": "🟡", "info": "🔵"}


def _findings_table(findings: list[dict]) -> str:
    """Render a list of findings as a GitHub Markdown table."""
    if not findings:
        return "_No issues found._"

    rows = ["| Severity | Category | Line | Message | Suggestion |", "|---|---|---|---|---|"]
    for f in sorted(findings, key=lambda x: _SEVERITY_ORDER.get(x.get("severity", "info"), 2)):
        emoji = _SEVERITY_EMOJI.get(f.get("severity", "info"), "🔵")
        sev = f.get("severity", "info")
        cat = str(f.get("category", "style")).capitalize()
        ln = f.get("line_number")
        line_str = str(ln) if ln is not None else "—"
        msg = str(f.get("message", "")).replace("|", "\\|")
        sug = str(f.get("suggestion", "")).replace("|", "\\|")
        rows.append(f"| {emoji} {sev} | {cat} | {line_str} | {msg} | {sug} |")

    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Node implementations (read-only state access; return partial updates only)
# ---------------------------------------------------------------------------


def _planner_impl(state: PRReviewState) -> dict:
    """Detect the primary programming language from the diff file headers."""
    language = _detect_language(state["pr_diff"])
    logger.info(
        "planner_node: detected language=%s for %s#%d",
        language,
        state["repo_name"],
        state["pr_number"],
    )
    return {"language": language}


def _code_quality_impl(state: PRReviewState) -> dict:
    """Run the CodeQualityAgent on the diff and store findings."""
    agent = CodeQualityAgent(llm=_get_llm())
    findings = agent.analyze(state["pr_diff"], language=state["language"])
    logger.info(
        "code_quality_node: %d finding(s) for %s#%d",
        len(findings),
        state["repo_name"],
        state["pr_number"],
    )
    return {"code_quality_findings": findings}


def _security_impl(state: PRReviewState) -> dict:
    """Static regex scan + LLM confirmation for security issues."""
    diff = state["pr_diff"]

    static_findings = _scan_security_patterns(diff)
    static_summary = (
        json.dumps(static_findings, indent=2) if static_findings else "None detected."
    )

    prompt = PromptTemplate(
        template=_SECURITY_PROMPT,
        input_variables=["diff", "static_findings"],
    )
    parser = JsonOutputParser()
    chain = prompt | _get_llm() | parser

    try:
        findings: list[dict] = chain.invoke(
            {"diff": diff, "static_findings": static_summary}
        )
        if not isinstance(findings, list):
            findings = static_findings
    except Exception as exc:
        logger.exception("security_node LLM call failed: %s", exc)
        findings = static_findings

    normalised: list[dict] = []
    for raw in findings:
        if not isinstance(raw, dict):
            continue
        ln = raw.get("line_number")
        try:
            ln = int(ln) if ln is not None else None
        except (TypeError, ValueError):
            ln = None

        severity = raw.get("severity", "warning")
        if severity not in {"critical", "warning", "info"}:
            severity = "warning"

        normalised.append(
            {
                "line_number": ln,
                "severity": severity,
                "category": "security",
                "message": str(raw.get("message", "")),
                "suggestion": str(raw.get("suggestion", "")),
            }
        )

    logger.info(
        "security_node: %d finding(s) for %s#%d",
        len(normalised),
        state["repo_name"],
        state["pr_number"],
    )
    return {"security_findings": normalised}


def _aggregator_impl(state: PRReviewState) -> dict:
    """Combine all findings and build the final Markdown summary."""
    cq = state.get("code_quality_findings") or []
    sec = state.get("security_findings") or []
    tst = state.get("test_findings") or []
    all_findings = cq + sec + tst

    total = len(all_findings)
    n_critical = sum(1 for f in all_findings if f.get("severity") == "critical")
    n_warning = sum(1 for f in all_findings if f.get("severity") == "warning")
    n_info = sum(1 for f in all_findings if f.get("severity") == "info")

    parts: list[str] = [
        "## 🤖 AI Code Review",
        "",
        f"**Repo:** `{state['repo_name']}` · **PR:** #{state['pr_number']} · "
        f"**Language:** {state['language']}",
        "",
        "### Summary",
        f"**{total} issue{'s' if total != 1 else ''} found:** "
        f"{n_critical} critical · {n_warning} warning{'s' if n_warning != 1 else ''} · {n_info} info",
        "",
    ]

    if state.get("error"):
        parts += ["### ⚠️ Errors", "", f"_{state['error']}_", ""]

    if cq:
        parts += ["### 🔍 Code Quality", "", _findings_table(cq), ""]
    if sec:
        parts += ["### 🔒 Security", "", _findings_table(sec), ""]
    if tst:
        parts += ["### 🧪 Test Coverage", "", _findings_table(tst), ""]

    if not all_findings:
        parts += ["### ✅ All Clear", "", "_No issues detected. Great work!_", ""]

    parts += [
        "---",
        "_Generated by [AI Code Review](https://github.com/apps/ai-code-review)_",
    ]

    final_summary = "\n".join(parts)

    logger.info(
        "aggregator_node: summary built (%d total findings) for %s#%d",
        total,
        state["repo_name"],
        state["pr_number"],
    )
    return {"final_summary": final_summary}


# ---------------------------------------------------------------------------
# Public node functions (traced + error-safe)
# ---------------------------------------------------------------------------


def planner_node(state: PRReviewState) -> dict:
    return _run_traced_node("planner_node", state, _planner_impl)


def code_quality_node(state: PRReviewState) -> dict:
    return _run_traced_node("code_quality_node", state, _code_quality_impl)


def security_node(state: PRReviewState) -> dict:
    return _run_traced_node("security_node", state, _security_impl)


def aggregator_node(state: PRReviewState) -> dict:
    return _run_traced_node("aggregator_node", state, _aggregator_impl)


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def _build_graph() -> Any:
    """Construct and compile the LangGraph review pipeline."""
    builder: StateGraph = StateGraph(PRReviewState)

    builder.add_node("planner_node", planner_node)
    builder.add_node("code_quality_node", code_quality_node)
    builder.add_node("security_node", security_node)
    builder.add_node("aggregator_node", aggregator_node)

    builder.add_edge(START, "planner_node")

    # Fan-out: two separate edges from planner → parallel nodes
    builder.add_edge("planner_node", "code_quality_node")
    builder.add_edge("planner_node", "security_node")

    # Fan-in: wait for both parallel nodes before aggregating
    builder.add_edge(["code_quality_node", "security_node"], "aggregator_node")

    builder.add_edge("aggregator_node", END)

    return builder.compile()


review_graph = _build_graph()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_review(
    pr_diff: str,
    repo_name: str,
    pr_number: int,
) -> PRReviewState:
    """Run the full PR review pipeline and return the completed state."""
    initial_state: PRReviewState = {
        "pr_diff": pr_diff,
        "repo_name": repo_name,
        "pr_number": pr_number,
        "language": "python",
        "code_quality_findings": [],
        "security_findings": [],
        "test_findings": [],
        "final_summary": "",
        "error": None,
        "agent_traces": [],
    }

    logger.info("run_review: starting for %s#%d", repo_name, pr_number)

    loop = asyncio.get_running_loop()
    final_state: PRReviewState = await loop.run_in_executor(
        None,
        lambda: review_graph.invoke(initial_state),
    )

    logger.info("run_review: completed for %s#%d", repo_name, pr_number)
    return final_state
