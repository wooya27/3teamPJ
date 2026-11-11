"""analyzer 단위 테스트 — 도구 출력 매핑을 subprocess Mock으로 검증.

실제 pylint/bandit 설치 없이 통과해야 한다(루트 가이드 §13).
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

from app import analyzer
from app.analyzer import _parse_diff, analyze

PY_DIFF = """diff --git a/src/db.py b/src/db.py
--- a/src/db.py
+++ b/src/db.py
@@ -0,0 +1,3 @@
+def q(name):
+    return f"SELECT * FROM users WHERE name = '{name}'"
+
"""


def _fake_proc(stdout: str):
    return SimpleNamespace(stdout=stdout, stderr="", returncode=1)


def test_parse_diff_reconstructs_post_image():
    files = _parse_diff(PY_DIFF)
    assert "src/db.py" in files
    content = files["src/db.py"]
    assert "def q(name):" in content
    assert "SELECT * FROM users" in content


def test_parse_diff_skips_deleted_file():
    deleted = (
        "diff --git a/gone.py b/gone.py\n"
        "--- a/gone.py\n"
        "+++ /dev/null\n"
        "@@ -1 +0,0 @@\n"
        "-print('x')\n"
    )
    assert _parse_diff(deleted) == {}


def test_empty_diff_returns_empty_result():
    issues, summary, ms = analyze("", "static_analysis")
    assert issues == []
    assert summary.critical == summary.major == summary.minor == 0
    assert ms >= 0


def test_security_maps_bandit_output_and_summary():
    bandit_json = json.dumps(
        {
            "results": [
                {
                    "issue_severity": "HIGH",
                    "line_number": 2,
                    "filename": "src/db.py",
                    "issue_text": "Possible SQL injection",
                    "test_id": "B608",
                    "more_info": "https://bandit.example/B608",
                }
            ]
        }
    )

    def fake_run(
    cmd,
    cwd,
    capture_output,
    text,
    timeout,
    encoding=None,
    errors=None
):
        if "bandit" in cmd:
            return _fake_proc(bandit_json)
        return _fake_proc("")  # semgrep 등 → 빈 출력

    with (
        patch.object(
            analyzer.subprocess,
            "run",
            side_effect=fake_run
        ),
        patch.object(
            analyzer,
            "_resolve_tool",
            side_effect=lambda name: [name]
        ),
        patch.object(
            analyzer,
            "_resolve_semgrep",
            return_value=["semgrep"]
        ),
    ):
        issues, summary, _ = analyze(
            PY_DIFF,
            "security_scan"
        )
       

    assert len(issues) == 1
    issue = issues[0]
    assert issue.severity == "Critical"
    assert issue.rule_id == "SEC-B608"
    assert issue.file == "src/db.py"
    assert summary.critical == 1


def test_static_maps_pylint_output():
    pylint_json = json.dumps(
        [
            {
                "type": "error",
                "line": 1,
                "path": "src/db.py",
                "message": "undefined name",
                "message-id": "E0602",
                "symbol": "undefined-variable",
            }
        ]
    )

    def fake_run(
    cmd,
    cwd,
    capture_output,
    text,
    timeout,
    encoding=None,
    errors=None
):
        if "pylint" in cmd:
            return _fake_proc(pylint_json)
        return _fake_proc("")  # radon → 빈 출력

    with (
        patch.object(
            analyzer.subprocess,
            "run",
            side_effect=fake_run
        ),
        patch.object(
            analyzer,
            "_resolve_tool",
            side_effect=lambda name: [name]
        ),
    ):
        issues, summary, _ = analyze(
            PY_DIFF,
            "static_analysis"
        )

    assert any(i.rule_id == "SA-E0602" and i.severity == "Critical" for i in issues)
    assert summary.critical == 1


def test_missing_tool_is_graceful_skip():
    with patch.object(analyzer.subprocess, "run", side_effect=FileNotFoundError):
        issues, summary, _ = analyze(PY_DIFF, "static_analysis")
    assert issues == []
    assert summary.major == 0


# ── 코드 스니펫 / 함수 / 프레임워크 추출 ──

FW_DIFF = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -0,0 +1,5 @@
+from fastapi import FastAPI
+
+def create_app():
+    app = FastAPI()
+    return app
"""


def test_code_for_issue_extracts_snippet_and_context():
    code_map = analyzer.extract_code_map(FW_DIFF)
    snippet, context = analyzer.code_for_issue(code_map, "src/app.py", 4)
    assert snippet.strip() == "app = FastAPI()"
    assert "def create_app():" in context  # 전후 문맥 포함


def test_code_for_issue_out_of_range_is_none():
    code_map = analyzer.extract_code_map(FW_DIFF)
    assert analyzer.code_for_issue(code_map, "src/app.py", 999) == (None, None)
    assert analyzer.code_for_issue(code_map, "nope.py", 1) == (None, None)


def test_function_at_finds_enclosing_def():
    code_map = analyzer.extract_code_map(FW_DIFF)
    assert analyzer.function_at(code_map, "src/app.py", 4) == "create_app"
    assert analyzer.function_at(code_map, "src/app.py", 3) == "create_app"  # def 라인 자신


def test_function_at_module_level_is_none():
    code_map = analyzer.extract_code_map(FW_DIFF)
    assert analyzer.function_at(code_map, "src/app.py", 1) is None  # import 라인


def test_framework_in_detects_fastapi():
    code_map = analyzer.extract_code_map(FW_DIFF)
    assert analyzer.framework_in(code_map, "src/app.py") == "FastAPI"


def test_pylint_suggestion_maps_to_korean():
    assert analyzer._pylint_suggestion("missing-module-docstring", "Missing module docstring") == (
        "모듈 최상단에 docstring을 추가하세요."
    )
    # 미등록 심볼 → 한글 폴백 문장
    fb = analyzer._pylint_suggestion("some-unknown-rule", "Some message")
    assert fb.endswith("수정하세요.")
    assert "pylint:" not in fb


def test_bandit_suggestion_maps_to_korean():
    assert "MD5" in analyzer._bandit_suggestion("B324", "Use of weak MD5 hash")
    assert "파라미터 바인딩" in analyzer._bandit_suggestion("B608", "sql")
    # 미등록 → 한글 폴백
    fb = analyzer._bandit_suggestion("B999", "Some risk")
    assert fb.endswith("수정하세요.")


def test_semgrep_suggestion_maps_to_korean():
    assert "SQL" in analyzer._semgrep_suggestion("python.lang.security.sql-injection", "")
    assert "XSS" in analyzer._semgrep_suggestion("rules.xss.reflected", "")
    # 미매칭 → 한글 폴백
    fb = analyzer._semgrep_suggestion("some.unknown.rule", "Generic finding")
    assert fb.endswith("수정하세요.")


def test_path_traversal_detects_candidate(tmp_path):
    file = tmp_path / "user.py"

    file.write_text(
        "file_path = BASE_DIR / filename",
        encoding="utf-8"
    )

    issues = analyzer._scan_path_traversal(
        ["user.py"],
        str(tmp_path)
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "SEC-PT001"
    assert issues[0].line == 1





def test_path_traversal_safe_code(tmp_path):
    file = tmp_path / "safe.py"

    file.write_text(
        'print("hello")',
        encoding="utf-8"
    )

    issues = analyzer._scan_path_traversal(
        ["safe.py"],
        str(tmp_path)
    )

    assert len(issues) == 0

def test_path_traversal_integrated():
    diff = """diff --git a/src/download.py b/src/download.py
--- /dev/null
+++ b/src/download.py
@@ -0,0 +1 @@
+file_path = BASE_DIR / filename
"""

    with (
        patch.object(analyzer, "_run_bandit", return_value=[]),
        patch.object(analyzer, "_run_semgrep", return_value=[]),
    ):
        issues, summary, _ = analyze(
            diff,
            "security_scan"
        )

    assert len(issues) == 1
    assert issues[0].rule_id == "SEC-PT001"
    assert issues[0].file == "src/download.py"
    assert summary.major == 1

def test_missing_auth_detects_unguarded_delete(tmp_path):
    file = tmp_path / "unsafe.py"

    file.write_text(
        "def delete_user(current_user_id, target_user_id):\n"
        "    if target_user_id in users:\n"
        "        del users[target_user_id]\n",
        encoding="utf-8"
    )

    issues = analyzer._scan_missing_auth(
        ["unsafe.py"],
        str(tmp_path)
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "SEC-AUTH001"
    assert issues[0].line == 3


def test_missing_auth_safe_code(tmp_path):
    file = tmp_path / "safe.py"

    file.write_text(
        "def delete_user(current_user_id, target_user_id):\n"
        "    if current_user_id == target_user_id:\n"
        "        del users[target_user_id]\n",
        encoding="utf-8"
    )

    issues = analyzer._scan_missing_auth(
        ["safe.py"],
        str(tmp_path)
    )

    assert len(issues) == 0



def test_missing_auth_integrated():
    diff = """diff --git a/src/user.py b/src/user.py
--- /dev/null
+++ b/src/user.py
@@ -0,0 +1,3 @@
+def delete_user(current_user_id, target_user_id):
+    if target_user_id in users:
+        del users[target_user_id]
"""

    with (
        patch.object(analyzer, "_run_bandit", return_value=[]),
        patch.object(analyzer, "_run_semgrep", return_value=[]),
    ):
        issues, summary, _ = analyze(
            diff,
            "security_scan"
        )

    assert any(
        issue.rule_id == "SEC-AUTH001"
        for issue in issues
    )
    assert summary.major >= 1

def test_compare_missing_auth_scanners(tmp_path):
    file = tmp_path / "sample.py"

    file.write_text(
        "def delete_user(current_user_id, target_user_id):\n"
        "    if target_user_id in users:\n"
        "        del users[target_user_id]\n",
        encoding="utf-8"
    )

    paths = ["sample.py"]
    cwd = str(tmp_path)

    bandit_issues = analyzer._run_bandit(paths, cwd)
    semgrep_issues = analyzer._run_semgrep(paths, cwd)
    custom_issues = analyzer._scan_missing_auth(paths, cwd)

    print(
        "Bandit:",
        [issue.rule_id for issue in bandit_issues]
    )

    print(
        "Semgrep:",
        [issue.rule_id for issue in semgrep_issues]
    )

    print(
        "직접 만든 스캐너:",
        [issue.rule_id for issue in custom_issues]
    )

    assert len(custom_issues) == 1
    assert custom_issues[0].rule_id == "SEC-AUTH001"

def test_hardcoded_secret_detects_candidate(tmp_path):
    file = tmp_path / "config.py"

    file.write_text(
        'API_KEY = "sk-example-not-a-real-key"',
        encoding="utf-8"
    )

    issues = analyzer._scan_hardcoded_secret(
        ["config.py"],
        str(tmp_path)
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "SEC-SECRET001"
    assert issues[0].line == 1

def test_hardcoded_secret_safe_code(tmp_path):
    file = tmp_path / "config.py"

    file.write_text(
        'import os\n'
        'API_KEY = os.getenv("API_KEY")\n',
        encoding="utf-8"
    )

    issues = analyzer._scan_hardcoded_secret(
        ["config.py"],
        str(tmp_path)
    )

    assert len(issues) == 0



def test_hardcoded_secret_integrated():
    diff = """diff --git a/src/config.py b/src/config.py
--- /dev/null
+++ b/src/config.py
@@ -0,0 +1 @@
+API_KEY = "example-secret"
"""

    with (
        patch.object(analyzer, "_run_bandit", return_value=[]),
        patch.object(analyzer, "_run_semgrep", return_value=[]),
    ):
        issues, summary, _ = analyze(
            diff,
            "security_scan"
        )

    assert any(
        issue.rule_id == "SEC-SECRET001"
        for issue in issues
    )

    assert summary.major >= 1