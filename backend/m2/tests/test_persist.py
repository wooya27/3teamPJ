"""result_persist.py 테스트 — review_issue INSERT 매핑·graceful.

실제 DB 없이 통과해야 한다(async 세션 팩토리를 Mock 주입).
"""

import pytest

from app.contract import build_agent_result
from app.services import result_persist
from app.services.result_persist import _issue_params, is_enabled, persist_issues
from shared.contracts import IssueItem, IssueSummary, M2AnalyzeRequest

PAYLOAD = M2AnalyzeRequest(task_id="t-1", pr_id="42", pr_diff="x", trace_id="pr_abc")


def _result(agent, issues):
    summary = IssueSummary()
    return build_agent_result(PAYLOAD, agent, issues, summary, 5)


class _FakeSession:
    def __init__(self, sink: list, raise_on_execute: bool = False):
        self._sink = sink
        self._raise = raise_on_execute
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, _sql, params):
        if self._raise:
            raise RuntimeError("db down")
        self._sink.append(params)

    async def commit(self):
        self.committed = True


def _factory(sink, raise_on_execute=False):
    def make():
        return _FakeSession(sink, raise_on_execute)

    return make


# ── 매핑 단위 ──

def test_issue_params_maps_severity_and_keyword():
    issue = IssueItem(severity="Critical", message="x", rule_id="SEC-B608", file="a/b.py")
    p = _issue_params(issue, "security_scan", "alice")
    assert p["severity"] == "critical"
    assert p["keyword"] == "security"
    assert p["github_id"] == "alice"
    assert p["agent"] == "security_scan"
    assert p["programming_language"] == "python"
    assert p["sub_category"] == "SQL injection"
    assert p["id"]  # uuid 생성됨


def test_severity_major_minor_mapping():
    major = _issue_params(IssueItem(severity="Major", message="m", rule_id="SA-X"), "static_analysis", "u")
    minor = _issue_params(IssueItem(severity="Minor", message="n", rule_id="SA-Y"), "static_analysis", "u")
    assert major["severity"] == "high"
    assert minor["severity"] == "medium"
    assert major["keyword"] == "static"


# ── persist_issues ──

@pytest.mark.asyncio
async def test_inserts_all_issues():
    issues = [
        IssueItem(severity="Critical", message="a", rule_id="SEC-B1", file="x.py"),
        IssueItem(severity="Major", message="b", rule_id="SA-C", file="y.py"),
    ]
    sink: list = []
    n = await persist_issues(_result("security_scan", issues), "alice", factory=_factory(sink))
    assert n == 2
    assert len(sink) == 2
    assert {p["severity"] for p in sink} == {"critical", "high"}


@pytest.mark.asyncio
async def test_skips_when_no_github_id():
    issues = [IssueItem(severity="Critical", message="a", rule_id="SEC-B1")]
    sink: list = []
    n = await persist_issues(_result("security_scan", issues), None, factory=_factory(sink))
    assert n == 0
    assert sink == []


@pytest.mark.asyncio
async def test_skips_when_no_issues():
    n = await persist_issues(_result("static_analysis", []), "alice", factory=_factory([]))
    assert n == 0


@pytest.mark.asyncio
async def test_none_result_is_zero():
    assert await persist_issues(None, "alice", factory=_factory([])) == 0


@pytest.mark.asyncio
async def test_graceful_on_db_error():
    issues = [IssueItem(severity="Critical", message="a", rule_id="SEC-B1")]
    n = await persist_issues(
        _result("security_scan", issues), "alice", factory=_factory([], raise_on_execute=True)
    )
    assert n == 0  # 예외를 삼키고 0 반환 (분석 비중단)


def test_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("M2_PERSIST_ENABLED", raising=False)
    assert is_enabled() is False


@pytest.mark.asyncio
async def test_disabled_path_does_not_touch_db(monkeypatch):
    # factory 미주입 + 비활성 → DB 접근 없이 0
    monkeypatch.delenv("M2_PERSIST_ENABLED", raising=False)
    issues = [IssueItem(severity="Critical", message="a", rule_id="SEC-B1")]
    n = await persist_issues(_result("security_scan", issues), "alice")
    assert n == 0


def test_severity_map_targets_are_valid_check_values():
    # review_issue CHECK: critical/high/medium/low
    assert set(result_persist._SEVERITY_MAP.values()) <= {"critical", "high", "medium", "low"}


# ── code_snippet / code_context / name_of_function / framework 채우기 ──

_FW_DIFF = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -0,0 +1,5 @@
+from fastapi import FastAPI
+
+def create_app():
+    app = FastAPI()
+    return app
"""


_FW_DIFF_WITH_REQS = _FW_DIFF + """diff --git a/requirements.txt b/requirements.txt
--- a/requirements.txt
+++ b/requirements.txt
@@ -0,0 +1,2 @@
+fastapi==0.110.1
+uvicorn>=0.29
"""

_PKG_JSON_DIFF = """diff --git a/package.json b/package.json
--- a/package.json
+++ b/package.json
@@ -0,0 +1,6 @@
+{
+  "dependencies": {
+    "react": "^18.2.0",
+    "next": "14.1.0"
+  }
+}
diff --git a/src/Btn.tsx b/src/Btn.tsx
--- a/src/Btn.tsx
+++ b/src/Btn.tsx
@@ -0,0 +1,2 @@
+import React from 'react'
+export const Btn = () => <button/>
"""


@pytest.mark.asyncio
async def test_persist_fills_code_columns_from_diff():
    issues = [IssueItem(severity="Major", message="x", rule_id="SA-W", file="src/app.py", line=4)]
    sink: list = []
    n = await persist_issues(
        _result("static_analysis", issues), "alice", factory=_factory(sink), pr_diff=_FW_DIFF
    )
    assert n == 1
    row = sink[0]
    assert row["code_snippet"].strip() == "app = FastAPI()"
    assert "def create_app():" in row["code_context"]
    assert row["name_of_function"] == "create_app"
    assert row["framework"] == "FastAPI"
    assert row["framework_version"] is None  # diff에 매니페스트 없음 → None


@pytest.mark.asyncio
async def test_framework_version_from_requirements():
    issues = [IssueItem(severity="Major", message="x", rule_id="SA-W", file="src/app.py", line=4)]
    sink: list = []
    await persist_issues(
        _result("static_analysis", issues), "alice",
        factory=_factory(sink), pr_diff=_FW_DIFF_WITH_REQS,
    )
    assert sink[0]["framework"] == "FastAPI"
    assert sink[0]["framework_version"] == "0.110.1"  # requirements.txt에서 추출


@pytest.mark.asyncio
async def test_framework_version_from_package_json():
    issues = [IssueItem(severity="Minor", message="x", rule_id="JS-W", file="src/Btn.tsx", line=2)]
    sink: list = []
    await persist_issues(
        _result("static_analysis", issues), "alice",
        factory=_factory(sink), pr_diff=_PKG_JSON_DIFF,
    )
    assert sink[0]["framework"] == "React"
    assert sink[0]["framework_version"] == "18.2.0"  # ^ 제거


def test_issue_params_without_code_map_leaves_columns_none():
    issue = IssueItem(severity="Minor", message="m", rule_id="SA-X", file="a.py", line=1)
    p = _issue_params(issue, "static_analysis", "u")
    assert p["code_snippet"] is None
    assert p["code_context"] is None
    assert p["name_of_function"] is None
    assert p["framework"] is None
