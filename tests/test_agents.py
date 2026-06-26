import json
from unittest.mock import MagicMock

import pytest

from agents.code_quality_agent import CodeQualityAgent

SAMPLE_PYTHON_DIFF = """\
--- a/auth.py
+++ b/auth.py
@@ -0,0 +1,8 @@
+def authenticate(username, password):
+    db_password = "admin123"
+    query = "SELECT * FROM users WHERE name = '" + username + "'"
+    if password == db_password:
+        return True
+    return False
"""


@pytest.fixture
def sample_python_diff() -> str:
    return SAMPLE_PYTHON_DIFF


def _llm_response(content: str) -> MagicMock:
    response = MagicMock()
    response.content = content
    return response


def test_code_quality_agent_finds_hardcoded_password(sample_python_diff):
    finding = [
        {
            "line_number": 2,
            "severity": "critical",
            "category": "security",
            "message": "Hardcoded password 'admin123' found in source code",
            "suggestion": "Load credentials from environment variables or a secrets manager",
        }
    ]
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _llm_response(json.dumps(finding))

    agent = CodeQualityAgent(mock_llm)
    results = agent.analyze(sample_python_diff)

    assert len(results) >= 1
    assert any(issue["severity"] == "critical" for issue in results)
    mock_llm.invoke.assert_called_once()


def test_code_quality_agent_handles_empty_diff():
    mock_llm = MagicMock()
    agent = CodeQualityAgent(mock_llm)

    results = agent.analyze("")

    assert results == []
    mock_llm.invoke.assert_not_called()


def test_code_quality_agent_retries_on_bad_json(sample_python_diff):
    valid_finding = [
        {
            "line_number": 3,
            "severity": "critical",
            "category": "security",
            "message": "SQL injection via string concatenation",
            "suggestion": "Use parameterized queries",
        }
    ]
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        _llm_response("not valid json"),
        _llm_response(json.dumps(valid_finding)),
    ]

    agent = CodeQualityAgent(mock_llm)
    results = agent.analyze(sample_python_diff)

    assert len(results) == 1
    assert results[0]["severity"] == "critical"
    assert results[0]["message"] == "SQL injection via string concatenation"
    assert mock_llm.invoke.call_count == 2
