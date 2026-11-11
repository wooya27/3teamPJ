"""m2 정적 분석·보안 스캔 — PR diff 기반 도구 실행.

계약: shared.contracts.IssueItem / IssueSummary / M2AnalyzeResponse.

m2 서비스는 오케스트레이터(m1)로부터 unified diff만 받는다(work_dir 없음).
따라서 diff의 post-image(추가·문맥 라인)를 임시 파일로 복원한 뒤 도구를 실행한다.

도구(pylint / radon / bandit / semgrep / eslint)가 설치돼 있지 않으면
빈 결과로 graceful skip 한다(루트 GLOBAL_AGENT_RULE / sub2 CLAUDE.md §12 —
도구 부재가 파이프라인을 막지 않는다).
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import ast
from pathlib import Path
from typing import Literal

from shared.contracts import IssueItem, IssueSummary

Agent = Literal["static_analysis", "security_scan"]

_TOOL_TIMEOUT = 30  # 초
_SUPPORTED_EXT = {".py", ".js", ".jsx", ".ts", ".tsx"}

_LANG_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

# 도구 severity → 계약 severity 매핑 (dev2 도구 정의와 동일)
_PYLINT_SEVERITY = {"E": "Critical", "F": "Critical", "W": "Major", "C": "Minor", "R": "Minor"}
_BANDIT_SEVERITY = {"HIGH": "Critical", "MEDIUM": "Major", "LOW": "Minor"}
_SEMGREP_SEVERITY = {"ERROR": "Critical", "WARNING": "Major", "INFO": "Minor"}
_ESLINT_SEVERITY = {2: "Critical", 1: "Major", 0: "Minor"}


# ── diff 파싱 ─────────────────────────────────────────────────────────────────

def _parse_diff(pr_diff: str) -> dict[str, str]:
    """unified diff → {relpath: post-image 내용}.

    post-image = 추가('+') 라인 + 문맥(' ') 라인. 삭제('-')는 제외한다.
    삭제된 파일(`+++ /dev/null`)은 건너뛴다.
    """
    files: dict[str, list[str]] = {}
    current: list[str] | None = None

    for line in pr_diff.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            current = None if (not path or path == "/dev/null") else files.setdefault(path, [])
            continue
        if line.startswith("--- ") or line.startswith("diff --git"):
            current = None
            continue
        if current is None:
            continue
        if line.startswith("@@") or line.startswith("\\"):
            continue
        if line.startswith("+"):
            current.append(line[1:])
        elif line.startswith(" "):
            current.append(line[1:])
        # 삭제('-')·기타 메타 라인은 무시

    return {rel: "\n".join(lines) + "\n" for rel, lines in files.items() if lines}


# ── 코드 스니펫 추출 ──────────────────────────────────────────────────────────
# 도구가 보고하는 line 번호는 post-image(=_parse_diff 결과) 기준이므로,
# 같은 post-image에서 해당 라인과 전후 문맥을 그대로 떼어내면 된다.

_CONTEXT_RADIUS = 3  # code_context에 포함할 이슈 라인 전후 줄 수


def extract_code_map(pr_diff: str) -> dict[str, list[str]]:
    """pr_diff의 post-image를 {relpath: [라인, ...]}로 반환 (snippet/context 추출용)."""
    return {rel: content.splitlines() for rel, content in _parse_diff(pr_diff or "").items()}


def code_for_issue(
    code_map: dict[str, list[str]],
    file: str | None,
    line: int | None,
    radius: int = _CONTEXT_RADIUS,
) -> tuple[str | None, str | None]:
    """이슈 위치(파일·라인)의 코드 한 줄(snippet)과 전후 문맥(context)을 추출한다.

    파일·라인 정보가 없거나 범위를 벗어나면 (None, None)을 반환한다(graceful).
    """
    if not file or not line or line < 1:
        return None, None
    lines = code_map.get(file)
    if not lines or line > len(lines):
        return None, None
    snippet = lines[line - 1]
    start = max(0, line - 1 - radius)
    end = min(len(lines), line + radius)
    context = "\n".join(lines[start:end])
    return snippet, context


# 이슈 라인을 감싸는 함수/클래스 이름 추출 (Python / JS·TS best-effort).
_PY_DEF_RE = re.compile(r"^(\s*)(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)")
_JS_FUNC_RE = re.compile(
    r"\bfunction\s+([A-Za-z_$][\w$]*)"
    r"|(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function\b|\()"
    r"|([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{"
)


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def function_at(
    code_map: dict[str, list[str]], file: str | None, line: int | None
) -> str | None:
    """이슈 라인을 감싸는 함수/클래스 이름. 못 찾으면 None(graceful)."""
    if not file or not line or line < 1:
        return None
    lines = code_map.get(file)
    if not lines or line > len(lines):
        return None
    target = line - 1
    ext = Path(file).suffix.lower()
    if ext == ".py":
        self_match = _PY_DEF_RE.match(lines[target])
        if self_match:
            return self_match.group(2)
        issue_indent = _indent_of(lines[target])
        for i in range(target - 1, -1, -1):
            m = _PY_DEF_RE.match(lines[i])
            if m and _indent_of(lines[i]) < issue_indent:
                return m.group(2)
        return None
    if ext in (".js", ".jsx", ".ts", ".tsx"):
        for i in range(target, -1, -1):
            m = _JS_FUNC_RE.search(lines[i])
            if m:
                return next((g for g in m.groups() if g), None)
        return None
    return None


# import 문에서 탐지할 주요 프레임워크 (모듈명 → 표기명).
_FRAMEWORK_MODULES = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "sqlalchemy": "SQLAlchemy",
    "pydantic": "Pydantic",
    "starlette": "Starlette",
    "tornado": "Tornado",
    "react": "React",
    "vue": "Vue",
    "@angular/core": "Angular",
    "next": "Next.js",
    "express": "Express",
    "svelte": "Svelte",
}


def framework_in(code_map: dict[str, list[str]], file: str | None) -> str | None:
    """파일 import 문에서 알려진 프레임워크를 탐지. 없으면 None(graceful)."""
    lines = code_map.get(file or "")
    if not lines:
        return None
    for raw in lines:
        s = raw.strip()
        for module, name in _FRAMEWORK_MODULES.items():
            base = module.split(".")[0]
            if (
                s.startswith(f"import {base}")
                or s.startswith(f"from {base}")
                or f"'{module}'" in s
                or f'"{module}"' in s
            ):
                return name
    return None


# 프레임워크 표기명 → (생태계, 패키지명). framework_version_in에서 매니페스트 조회용.
_FRAMEWORK_PKG = {
    "FastAPI": ("pip", "fastapi"),
    "Flask": ("pip", "flask"),
    "Django": ("pip", "django"),
    "SQLAlchemy": ("pip", "sqlalchemy"),
    "Pydantic": ("pip", "pydantic"),
    "Starlette": ("pip", "starlette"),
    "Tornado": ("pip", "tornado"),
    "React": ("npm", "react"),
    "Vue": ("npm", "vue"),
    "Angular": ("npm", "@angular/core"),
    "Next.js": ("npm", "next"),
    "Express": ("npm", "express"),
    "Svelte": ("npm", "svelte"),
}


def _npm_version(text: str, pkg: str) -> str | None:
    """package.json의 `"pkg": "^1.2.3"`에서 버전 추출(범위 연산자 제거)."""
    m = re.search(rf'"{re.escape(pkg)}"\s*:\s*"([^"]+)"', text)
    if not m:
        return None
    return re.sub(r"^[\^~>=<\s]+", "", m.group(1)) or None


def _pip_version(text: str, pkg: str) -> str | None:
    """requirements.txt / pyproject.toml에서 pkg 버전 추출(여러 표기 시도)."""
    p = re.escape(pkg)
    patterns = (
        rf"(?im)^\s*{p}\s*(?:==|>=|~=|<=|!=|===|<|>)\s*v?([0-9][\w.\-]*)",  # requirements
        rf'(?im)^\s*{p}\s*=\s*"[\^~>=<!\s]*v?([0-9][\w.\-]*)"',            # poetry: pkg = "^1.2"
        rf'(?i)"{p}\s*(?:==|>=|~=|<=|!=|===|<|>)\s*v?([0-9][\w.\-]*)"',     # PEP621: "pkg>=1.2"
    )
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return None


def framework_version_in(
    code_map: dict[str, list[str]], framework: str | None
) -> str | None:
    """diff에 매니페스트(package.json/requirements.txt/pyproject.toml)가 있으면
    탐지된 framework의 버전을 추출한다. 없으면 None(graceful)."""
    spec = _FRAMEWORK_PKG.get(framework or "")
    if not spec:
        return None
    ecosystem, pkg = spec
    for path, lines in code_map.items():
        base = path.rsplit("/", 1)[-1].lower()
        text = "\n".join(lines)
        if ecosystem == "npm" and base == "package.json":
            v = _npm_version(text, pkg)
            if v:
                return v
        elif ecosystem == "pip" and (
            base.startswith("requirements") or base == "pyproject.toml"
        ):
            v = _pip_version(text, pkg)
            if v:
                return v
    return None


def _materialize(files: dict[str, str], root: str) -> list[str]:
    """복원된 파일을 임시 디렉토리에 기록 → 기록된 상대경로 목록 반환."""
    written: list[str] = []
    for rel, content in files.items():
        if Path(rel).suffix.lower() not in _SUPPORTED_EXT:
            continue
        abs_path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(abs_path) or root, exist_ok=True)
        Path(abs_path).write_text(content, encoding="utf-8")
        written.append(rel)
    return written


def _group_by_lang(paths: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for p in paths:
        lang = _LANG_BY_EXT.get(Path(p).suffix.lower(), "unknown")
        groups.setdefault(lang, []).append(p)
    return groups


def _scan_path_traversal(
    paths: list[str],
    cwd: str
) -> list[IssueItem]:

    issues = []

    for path in paths:
        file_path = Path(cwd) / path

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)

        except (OSError, UnicodeDecodeError, SyntaxError):
            continue

        for node in ast.walk(tree):

            if not isinstance(node, ast.BinOp):
                continue

            if not isinstance(node.op, ast.Div):
                continue

            if not isinstance(node.left, ast.Name):
                continue

            if node.left.id not in {"BASE_DIR", "BACKUP_DIR"}:
                continue

            if not isinstance(node.right, ast.Name):
                continue

            issues.append(
                IssueItem(
                    severity="Major",
                    line=node.lineno,
                    file=path,
                    message="경로 검증이 필요한 코드 발견",
                    rule_id="SEC-PT001",
                    suggestion="사용자 입력 경로의 안전성을 확인하세요."
                )
            )

    return issues


def _scan_missing_auth(
    paths: list[str],
    cwd: str
) -> list[IssueItem]:

    issues = []

    for path in paths:
        file_path = Path(cwd) / path

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)

        except (OSError, UnicodeDecodeError, SyntaxError):
            continue

        for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue

                guarded_lines = set()

                for child in ast.walk(node):
                    if isinstance(child, ast.If):
                        condition = ast.unparse(child.test)

                        if condition in (
                            "current_user_id == target_user_id",
                            "target_user_id == current_user_id"
                        ):
                            for statement in child.body:
                                for part in ast.walk(statement):
                                    if isinstance(part, ast.Delete):
                                        guarded_lines.add(part.lineno)

                for child in ast.walk(node):
                        if not isinstance(child, ast.Delete):
                            continue

                        is_user_delete = False

                        for target in child.targets:
                            if not isinstance(target, ast.Subscript):
                                continue

                            container = target.value

                            if (
                                isinstance(container, ast.Name)
                                and container.id == "users"
                            ) or (
                                isinstance(container, ast.Attribute)
                                and isinstance(container.value, ast.Name)
                                and container.value.id == "self"
                                and container.attr == "users"
                            ):
                                is_user_delete = True

                        if not is_user_delete:
                            continue

                        if child.lineno not in guarded_lines:
                            issues.append(
                                IssueItem(
                                    severity="Major",
                                    line=child.lineno,
                                    file=path,
                                    message="인가 누락이 의심되는 삭제 작업",
                                    rule_id="SEC-AUTH001",
                                    suggestion="삭제 전에 사용자 권한을 확인하세요."
                                )
                            )
                            

    return issues

def _scan_hardcoded_secret(
    paths: list[str],
    cwd: str
) -> list[IssueItem]:

    issues = []

    secret_names = {
        "API_KEY",
        "PASSWORD",
        "TOKEN"
    }

    for path in paths:
        file_path = Path(cwd) / path

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)

        except (OSError, UnicodeDecodeError, SyntaxError):
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue

            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue

                name = target.id.upper()

                if not (
                    name in secret_names
                    or any(
                        name.endswith("_" + keyword)
                        for keyword in secret_names
                    )
                ):
                    continue

                if (
                    isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                    and node.value.value
                ):
                    issues.append(
                        IssueItem(
                            severity="Major",
                            line=node.lineno,
                            file=path,
                            message="하드코딩된 비밀정보 의심",
                            rule_id="SEC-SECRET001",
                            suggestion="비밀정보를 환경변수 등으로 관리하세요."
                        )
                    )

    return issues

# ── 도구 실행 ─────────────────────────────────────────────────────────────────

def _run(cmd: list[str], cwd: str) -> str | None:
    """서브프로세스 실행 → stdout 반환. 도구 부재·타임아웃 시 None(graceful skip)."""
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=_TOOL_TIMEOUT
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout


def _relativize(path: str, root: str) -> str:
    if path and os.path.isabs(path):
        try:
            path = os.path.relpath(path, root)
        except ValueError:
            pass
    normalized = (path or "").replace(os.sep, "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _resolve_semgrep() -> list[str] | None:
    """실행 가능한 semgrep 커맨드. Windows 네이티브 등 미지원 환경은 None."""
    exe = shutil.which("semgrep")
    if exe:
        return [exe]
    if os.name == "nt":
        return None
    if importlib.util.find_spec("semgrep") is not None:
        return [sys.executable, "-m", "semgrep"]
    return None


def _resolve_tool(name: str) -> list[str] | None:
    """시스템 PATH에서 도구 바이너리를 찾고, 없으면 sys.executable -m 으로 폴백."""
    exe = shutil.which(name)
    if exe:
        return [exe]
    # venv 외부 시스템 Python으로도 시도
    try:
        subprocess.run([sys.executable, "-m", name, "--version"],
                       capture_output=True, timeout=5)
        return [sys.executable, "-m", name]
    except Exception:
        return None


# pylint 룰 심볼 → 한글 권장 문구. 미등록 심볼은 _pylint_suggestion에서 폴백.
_PYLINT_SUGGESTIONS = {
    "missing-module-docstring": "모듈 최상단에 docstring을 추가하세요.",
    "missing-class-docstring": "클래스에 docstring을 추가하세요.",
    "missing-function-docstring": "함수에 docstring을 추가하세요.",
    "unused-import": "사용하지 않는 import를 제거하세요.",
    "unused-variable": "사용하지 않는 변수를 제거하세요.",
    "unused-argument": "사용하지 않는 인자를 제거하거나 활용하세요.",
    "line-too-long": "한 줄이 너무 깁니다 — 줄을 적절히 나누세요.",
    "trailing-whitespace": "줄 끝의 불필요한 공백을 제거하세요.",
    "invalid-name": "명명 규칙(snake_case 등)에 맞게 이름을 변경하세요.",
    "too-many-arguments": "인자 수가 너무 많습니다 — 객체나 데이터클래스로 묶으세요.",
    "too-many-locals": "지역 변수가 너무 많습니다 — 함수를 분리하세요.",
    "too-many-branches": "분기가 너무 많습니다 — 로직을 단순화하세요.",
    "too-many-statements": "구문이 너무 많습니다 — 함수를 더 작게 나누세요.",
    "broad-except": "광범위한 except 대신 구체적인 예외 타입을 잡으세요.",
    "bare-except": "except에 잡을 예외 타입을 명시하세요.",
    "redefined-outer-name": "외부 스코프 이름을 가립니다 — 변수명을 변경하세요.",
    "import-error": "import 경로를 확인하세요 — 모듈을 찾을 수 없습니다.",
    "no-member": "존재하지 않는 속성에 접근합니다 — 속성명을 확인하세요.",
    "undefined-variable": "정의되지 않은 변수입니다 — 선언을 확인하세요.",
    "f-string-without-interpolation": "보간이 없는 f-string입니다 — 일반 문자열로 바꾸세요.",
    "logging-fstring-interpolation": "로깅은 % 포매팅 등 지연 평가 방식을 사용하세요.",
    "consider-using-with": "리소스는 with 문으로 관리하세요.",
    "wrong-import-order": "import 순서를 표준에 맞게 정렬하세요.",
    "too-few-public-methods": "공개 메서드가 적습니다 — 클래스 설계를 재검토하세요.",
    "no-else-return": "else 없이 바로 return하도록 단순화하세요.",
    "dangerous-default-value": "가변 객체를 기본 인자로 쓰지 마세요(None 후 내부 생성).",
}


def _pylint_suggestion(symbol: str, message: str) -> str:
    """pylint 룰 심볼을 한글 권장 문구로. 미등록이면 원문 메시지를 한글 문장에 담는다."""
    mapped = _PYLINT_SUGGESTIONS.get(symbol)
    if mapped:
        return mapped
    if message:
        return f"{message.rstrip('.')} — 해당 코드를 수정하세요."
    return "pylint 규칙 위반 — 해당 코드를 수정하세요."


def _run_pylint(paths: list[str], cwd: str) -> list[IssueItem]:
    cmd = _resolve_tool("pylint")
    if cmd is None:
        return []
    out = _run([*cmd, "--output-format=json", "--score=no", *paths], cwd)
    if not out:
        return []
    try:
        raw = json.loads(out)
    except json.JSONDecodeError:
        return []
    return [
        IssueItem(
            severity=_PYLINT_SEVERITY.get(str(i.get("type", "W"))[:1].upper(), "Minor"),
            line=i.get("line"),
            file=i.get("path"),
            message=i.get("message", ""),
            rule_id=f"SA-{i.get('message-id', 'UNKNOWN')}",
            suggestion=_pylint_suggestion(i.get("symbol", ""), i.get("message", "")),
        )
        for i in raw
    ]


def _run_radon(paths: list[str], cwd: str) -> list[IssueItem]:
    cmd = _resolve_tool("radon")
    if cmd is None:
        return []
    out = _run([*cmd, "cc", "--json", "--min", "B", *paths], cwd)
    if not out:
        return []
    try:
        raw = json.loads(out)
    except json.JSONDecodeError:
        return []
    items: list[IssueItem] = []
    for filepath, funcs in raw.items():
        if not isinstance(funcs, list):
            continue
        for func in funcs:
            cc = func.get("complexity", 0)
            if cc > 10:
                items.append(
                    IssueItem(
                        severity="Major",
                        line=func.get("lineno"),
                        file=filepath,
                        message=f"순환복잡도 {cc} 감지 (함수: {func.get('name')})",
                        rule_id="SA-COMPLEXITY",
                        suggestion="함수를 더 작은 단위로 분리하세요.",
                    )
                )
    return items


def _run_eslint(paths: list[str], cwd: str) -> list[IssueItem]:
    out = _run(["eslint", "--format=json", *paths], cwd)
    if not out:
        return []
    try:
        raw = json.loads(out)
    except json.JSONDecodeError:
        return []
    items: list[IssueItem] = []
    for file_result in raw:
        rel = _relativize(file_result.get("filePath", ""), cwd)
        for msg in file_result.get("messages", []):
            items.append(
                IssueItem(
                    severity=_ESLINT_SEVERITY.get(msg.get("severity", 1), "Minor"),
                    line=msg.get("line"),
                    file=rel,
                    message=msg.get("message", ""),
                    rule_id=f"JS-{msg.get('ruleId') or 'UNKNOWN'}",
                    suggestion=(
                        f"{msg.get('message', '').rstrip('.')} — 해당 규칙에 맞게 수정하세요."
                        if msg.get("message")
                        else "ESLint 규칙 위반 — 해당 코드를 수정하세요."
                    ),
                )
            )
    return items


# bandit test_id → 한글 권장. 미등록 ID는 _bandit_suggestion에서 폴백.
_BANDIT_SUGGESTIONS = {
    "B102": "exec 사용은 코드 인젝션 위험이 큽니다 — 사용을 피하세요.",
    "B104": "모든 인터페이스(0.0.0.0) 바인딩을 피하고 필요한 주소만 바인딩하세요.",
    "B105": "하드코딩된 비밀번호/시크릿입니다 — 환경변수나 시크릿 매니저로 옮기세요.",
    "B106": "함수 인자로 하드코딩된 시크릿을 넘기고 있습니다 — 외부 설정으로 분리하세요.",
    "B107": "기본 인자에 하드코딩된 시크릿이 있습니다 — 외부 설정으로 분리하세요.",
    "B108": "하드코딩된 임시 디렉터리 대신 tempfile 모듈을 사용하세요.",
    "B110": "except: pass로 예외를 삼키지 마세요 — 최소한 로깅하세요.",
    "B112": "except 후 continue로 예외를 무시하지 마세요 — 처리하거나 로깅하세요.",
    "B201": "운영 환경에서는 Flask debug=True를 끄세요.",
    "B301": "신뢰할 수 없는 데이터의 pickle 역직렬화는 위험합니다 — json 등 안전한 포맷을 쓰세요.",
    "B303": "취약한 해시(MD5 등)입니다 — SHA-256 이상, 비밀번호엔 bcrypt/argon2를 쓰세요.",
    "B304": "취약한 암호화 알고리즘입니다 — AES 등 안전한 방식을 쓰세요.",
    "B305": "취약한 암호화 모드입니다 — AES-GCM 등 인증 암호화를 쓰세요.",
    "B307": "eval 사용은 코드 인젝션 위험이 큽니다 — ast.literal_eval 등으로 대체하세요.",
    "B311": "보안 목적 난수는 예측 가능한 random 대신 secrets 모듈을 쓰세요.",
    "B324": "취약한 해시 알고리즘(MD5/SHA1)입니다 — SHA-256 이상, 비밀번호엔 bcrypt/argon2를 쓰세요.",
    "B501": "인증서 검증(verify)을 비활성화하지 마세요.",
    "B506": "yaml.load 대신 yaml.safe_load를 사용하세요.",
    "B601": "셸 명령 실행은 명령 인젝션 위험 — 파라미터화된 호출을 쓰세요.",
    "B602": "shell=True는 명령 인젝션 위험 — shell=False와 인자 리스트를 쓰세요.",
    "B603": "외부 입력으로 프로세스를 실행할 때 입력을 검증하고 shell=False를 쓰세요.",
    "B604": "셸을 경유한 함수 호출은 명령 인젝션 위험 — shell=False를 쓰세요.",
    "B605": "셸로 프로세스를 시작하면 명령 인젝션 위험 — 인자 리스트로 직접 실행하세요.",
    "B607": "부분 경로로 프로세스를 실행하면 PATH 조작 위험 — 절대경로를 쓰세요.",
    "B608": "SQL을 문자열로 조합하지 말고 파라미터 바인딩(플레이스홀더)을 사용하세요.",
    "B610": "Django ORM에서 raw SQL 조합 대신 파라미터 바인딩을 사용하세요.",
    "B701": "Jinja2 autoescape를 활성화해 XSS를 방지하세요.",
}


def _bandit_suggestion(test_id: str, issue_text: str) -> str:
    """bandit test_id를 한글 권장 문구로. 미등록이면 한글 폴백."""
    mapped = _BANDIT_SUGGESTIONS.get(test_id)
    if mapped:
        return mapped
    if issue_text:
        return f"{issue_text.rstrip('.')} — 안전하게 수정하세요."
    return f"보안 점검 필요({test_id}) — 해당 코드를 안전하게 수정하세요."


def _run_bandit(paths: list[str], cwd: str) -> list[IssueItem]:
    cmd = _resolve_tool("bandit")
    if cmd is None:
        return []
    out = _run([*cmd, "-r", "-f", "json", *paths], cwd)
    if out is None:
        return []
    try:
        raw = json.loads(out or "{}")
    except json.JSONDecodeError:
        return []
    return [
        IssueItem(
            severity=_BANDIT_SEVERITY.get(i.get("issue_severity", "LOW"), "Minor"),
            line=i.get("line_number"),
            file=i.get("filename"),
            message=i.get("issue_text", ""),
            rule_id=f"SEC-{i.get('test_id', 'UNKNOWN')}",
            suggestion=_bandit_suggestion(i.get("test_id", ""), i.get("issue_text", "")),
        )
        for i in raw.get("results", [])
    ]


# semgrep check_id에 포함된 키워드 → 한글 권장 (위에서부터 우선 매칭).
_SEMGREP_SUGGESTION_KEYWORDS = (
    ("sql", "SQL 인젝션 위험 — 문자열 조합 대신 파라미터 바인딩을 사용하세요."),
    ("xss", "XSS 위험 — 출력 값에 이스케이프/인코딩을 적용하세요."),
    ("ssrf", "SSRF 위험 — 외부 요청 대상 URL을 화이트리스트로 제한하세요."),
    ("path-traversal", "경로 조작 위험 — 입력 경로를 정규화·검증하세요."),
    ("command", "명령 인젝션 위험 — 셸 호출을 피하고 입력을 검증하세요."),
    ("os-command", "명령 인젝션 위험 — 셸 호출을 피하고 입력을 검증하세요."),
    ("exec", "동적 코드 실행 위험 — exec/eval 사용을 피하세요."),
    ("deserial", "안전하지 않은 역직렬화 — 신뢰된 데이터만 처리하세요."),
    ("pickle", "신뢰할 수 없는 pickle 역직렬화는 위험 — 안전한 포맷을 쓰세요."),
    ("hardcoded", "하드코딩된 시크릿 — 환경변수/시크릿 매니저로 옮기세요."),
    ("secret", "하드코딩된 시크릿 — 환경변수/시크릿 매니저로 옮기세요."),
    ("crypto", "취약한 암호화 — 강력한 알고리즘과 모드를 사용하세요."),
    ("weak-hash", "취약한 해시 — SHA-256 이상, 비밀번호엔 bcrypt/argon2를 쓰세요."),
    ("md5", "취약한 해시(MD5) — SHA-256 이상, 비밀번호엔 bcrypt/argon2를 쓰세요."),
    ("csrf", "CSRF 보호를 활성화하세요."),
    ("redirect", "오픈 리다이렉트 위험 — 리다이렉트 대상을 검증하세요."),
    ("traversal", "경로/디렉터리 조작 위험 — 입력을 검증하세요."),
    ("injection", "인젝션 위험 — 외부 입력을 신뢰하지 말고 검증·이스케이프하세요."),
)


def _semgrep_suggestion(check_id: str, message: str) -> str:
    """semgrep check_id 키워드를 한글 권장으로. 미매칭이면 한글 폴백."""
    cid = (check_id or "").lower()
    for needle, text in _SEMGREP_SUGGESTION_KEYWORDS:
        if needle in cid:
            return text
    if message:
        return f"{message.rstrip('.')} — 안전하게 수정하세요."
    return "보안 취약점이 감지되었습니다 — 해당 코드를 안전하게 수정하세요."


def _run_semgrep(paths: list[str], cwd: str) -> list[IssueItem]:
    cmd = _resolve_semgrep()
    if cmd is None:
        return []
    out = _run([*cmd, "--config=p/owasp-top-ten", "--json", *paths], cwd)
    if not out:
        return []
    try:
        raw = json.loads(out)
    except json.JSONDecodeError:
        return []
    return [
        IssueItem(
            severity=_SEMGREP_SEVERITY.get(
                i.get("extra", {}).get("severity", "WARNING"), "Major"
            ),
            line=i.get("start", {}).get("line"),
            file=i.get("path"),
            message=i.get("extra", {}).get("message", ""),
            rule_id=f"OWASP-{str(i.get('check_id', 'UNKNOWN')).split('.')[-1]}",
            suggestion=_semgrep_suggestion(
                str(i.get("check_id", "")), i.get("extra", {}).get("message", "")
            ),
        )
        for i in raw.get("results", [])
    ]


def _run_tools(rel_paths: list[str], cwd: str, agent: Agent) -> list[IssueItem]:
    issues: list[IssueItem] = []
    for lang, paths in _group_by_lang(rel_paths).items():
        if agent == "static_analysis":
            if lang == "python":
                issues += _run_pylint(paths, cwd)
                issues += _run_radon(paths, cwd)
            elif lang in ("javascript", "typescript"):
                issues += _run_eslint(paths, cwd)
        else:  # security_scan
            if lang == "python":
                issues += _run_bandit(paths, cwd)
                issues += _run_semgrep(paths, cwd)
                issues += _scan_path_traversal(paths, cwd)
                issues += _scan_missing_auth(paths, cwd)
                issues += _scan_hardcoded_secret(paths, cwd)
            else:
                issues += _run_semgrep(paths, cwd)
    return issues


def _summarize(issues: list[IssueItem]) -> IssueSummary:
    summary = IssueSummary()
    for issue in issues:
        if issue.severity == "Critical":
            summary.critical += 1
        elif issue.severity == "Major":
            summary.major += 1
        else:
            summary.minor += 1
    return summary




# ── 공개 진입점 ───────────────────────────────────────────────────────────────

def analyze(pr_diff: str, agent: Agent) -> tuple[list[IssueItem], IssueSummary, int]:
    """PR diff를 분석해 (이슈 목록, 요약, 실행시간 ms)를 반환한다.

    diff가 비었거나 지원 파일이 없으면 빈 결과를 반환한다.
    """
    start = time.monotonic()
    files = _parse_diff(pr_diff or "")
    if not files:
        return [], IssueSummary(), int((time.monotonic() - start) * 1000)

    tmp = tempfile.mkdtemp(prefix="m2-")
    try:
        written = _materialize(files, tmp)
        issues = _run_tools(written, tmp, agent)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    for issue in issues:
        issue.file = _relativize(issue.file or "", tmp)

    return issues, _summarize(issues), int((time.monotonic() - start) * 1000)



