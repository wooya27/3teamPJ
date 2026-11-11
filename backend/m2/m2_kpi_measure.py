"""Code Shepherd M2: 6개 혼합 케이스의 취약점 유형별 KPI를 측정한다.

사용 위치: 3teamPJ/backend/m2/m2_kpi_measure.py
실행 방법: uv run --extra analysis python m2_kpi_measure.py

주의: 타입 단위(케이스 × 취약점 유형) 평가이므로 코드 줄 단위 탐지율과 다르다.
이 스크립트는 DB, GitHub 원격 저장소, 기존 프로젝트 코드를 변경하지 않는다.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from app.analyzer import analyze, _resolve_semgrep, _resolve_tool

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "tests" / "m2_mixed_case"
OUTPUT_DIR = ROOT / "kpi_outputs"

# expected_issue.json의 레거시 규칙 ID → 비교용 취약점 유형
EXPECTED_TYPE = {
    "SEC-001": "SQLI",     # SQL 인젝션
    "SEC-003": "PATH",     # 경로 탐색
    "SEC-004": "COMMAND",  # 명령 인젝션
    "SEC-005": "MD5",      # 취약한 MD5 비밀번호 해싱
    "SEC-006": "SECRET",   # 하드코딩된 비밀정보
    "AUTH-001": "AUTH",    # 인가 누락
}
TYPES = tuple(EXPECTED_TYPE.values())


def actual_type(rule_id: str | None) -> str | None:
    """M2/Bandit/Semgrep 규칙 ID를 6종 취약점 유형으로 통일한다."""
    rid = (rule_id or "").lower()
    if rid == "sec-pt001" or "traversal" in rid:
        return "PATH"
    if rid == "sec-auth001" or "authorization" in rid or "missing-auth" in rid:
        return "AUTH"
    if rid == "sec-secret001" or rid in {"sec-b105", "sec-b106", "sec-b107"}:
        return "SECRET"
    if rid in {"sec-b303", "sec-b324"} or "md5" in rid:
        return "MD5"
    if rid == "sec-b608" or "sql-injection" in rid or "sql_injection" in rid:
        return "SQLI"
    if rid in {"sec-b602", "sec-b604", "sec-b605"} or "command-injection" in rid or "os-command" in rid:
        return "COMMAND"
    if rid.startswith("owasp-"):
        if "secret" in rid or "hardcoded" in rid:
            return "SECRET"
        if "sql" in rid and ("inject" in rid or "query" in rid):
            return "SQLI"
        if "shell" in rid or "command" in rid:
            return "COMMAND"
        if "auth" in rid and "oauth" not in rid:
            return "AUTH"
    return None


def to_diff(case_id: str, content: str) -> str:
    """테스트 파일 내용을 실제 M2가 사용하는 신규 파일 PR diff 형태로 만든다."""
    lines = content.splitlines()
    header = f"--- /dev/null\n+++ b/{case_id}/vulnerable.py\n@@ -0,0 +1,{len(lines)} @@\n"
    return header + "\n".join("+" + line for line in lines) + "\n"


def percentage(n: int, d: int) -> float | None:
    return round(100.0 * n / d, 2) if d else None


def main() -> None:
    # 분석기가 외부 도구를 건너뛰면 KPI가 왜곡되므로 사전 확인한다.
    if _resolve_semgrep() is None:
        raise SystemExit("Semgrep 실행 파일을 찾지 못했습니다. uv run --extra analysis로 실행했는지 확인하세요.")
    if _resolve_tool("bandit") is None:
        raise SystemExit("Bandit 실행 파일을 찾지 못했습니다. uv run --extra analysis로 실행했는지 확인하세요.")
    print("확인: Bandit + Semgrep 실행 경로 사용 가능")
    case_dirs = sorted(DATA_DIR.glob("mixed_case_0[1-6]"))
    if len(case_dirs) != 6:
        raise SystemExit(f"평가 데이터 오류: 6개 케이스가 필요하지만 {len(case_dirs)}개 발견")

    detail = []
    tp = fp = fn = tn = 0
    times_ms = []
    uncategorized = 0

    for folder in case_dirs:
        case_id = folder.name
        expected_path = folder / "expected_issue.json"
        vulnerable_path = folder / "vulnerable.py"
        if not expected_path.is_file() or not vulnerable_path.is_file():
            raise SystemExit(f"평가 데이터 파일이 없습니다: {case_id}")

        raw_expected = json.loads(expected_path.read_text(encoding="utf-8"))
        expected_ids = [x["rule_id"] for x in raw_expected["expected_issues"]]
        unexpected_ids = sorted(set(expected_ids) - set(EXPECTED_TYPE))
        if unexpected_ids:
            raise SystemExit(f"미정의 정답 규칙 ID({case_id}): {unexpected_ids}")

        expected_types = {EXPECTED_TYPE[rid] for rid in expected_ids}
        if len(expected_types) != len(expected_ids):
            raise SystemExit(f"같은 유형이 여러 건인 케이스({case_id}): 유형 단위 평가 불가")

        content = vulnerable_path.read_text(encoding="utf-8")
        issues, _summary, execution_ms = analyze(to_diff(case_id, content), "security_scan")
        times_ms.append(execution_ms)

        detected_types = {mapped for x in issues if (mapped := actual_type(x.rule_id))}
        unmatched = sorted(detected_types - expected_types)
        found = sorted(detected_types & expected_types)
        missed = sorted(expected_types - detected_types)
        other = [x.rule_id for x in issues if actual_type(x.rule_id) is None]
        uncategorized += len(other)

        case_tp = len(found)
        case_fp = len(unmatched)
        case_fn = len(missed)
        case_tn = len(set(TYPES) - expected_types - detected_types)
        tp += case_tp
        fp += case_fp
        fn += case_fn
        tn += case_tn

        detail.append({
            "case": case_id,
            "expected_types": sorted(expected_types),
            "detected_types": sorted(detected_types),
            "matched": found,
            "missed": missed,
            "unexpected_type_alerts": unmatched,
            "raw_security_issues": [
                {"rule_id": x.rule_id, "line": x.line, "type": actual_type(x.rule_id)}
                for x in issues
            ],
            "unclassified_rule_ids": other,
            "analysis_ms": execution_ms,
        })
        print(f"{case_id}: 정답 {len(expected_types)}, 일치 {case_tp}, 미탐 {case_fn}, 추가 경고 {case_fp}, {execution_ms / 1000:.2f}초")

    metrics = {
        "comparison_unit": "case x vulnerability type (6 cases x 6 types = 36 labels)",
        "tp": tp,
        "fn": fn,
        "fp_provisional": fp,
        "tn_provisional": tn,
        "recall_pct": percentage(tp, tp + fn),
        "precision_pct_provisional": percentage(tp, tp + fp),
        "false_positive_rate_pct_provisional": percentage(fp, fp + tn),
        "avg_scan_seconds": round(mean(times_ms) / 1000, 3),
        "min_scan_seconds": round(min(times_ms) / 1000, 3),
        "max_scan_seconds": round(max(times_ms) / 1000, 3),
        "unclassified_issue_count": uncategorized,
    }
    result = {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "cases": detail,
        "warnings": [
            "정답(expected_issues)은 21개의 유형별 라벨이며, 줄 단위 탐지율을 뜻하지 않습니다.",
            "추가 경고(FP)는 정답에 없는 유형이라는 의미이며, 실제 오탐인지 사람의 재검토가 필요합니다.",
            "분류되지 않은 규칙은 정밀도/오탐률 계산에서 제외했습니다.",
            "분석 시간은 로컬 환경에서 각 케이스를 1회 실행한 시간입니다. 수동 검토시간 절감률이 아닙니다.",
            "도구가 미설치/타임아웃이면 M2가 해당 도구를 건너뛸 수 있어 환경에 따라 결과가 달라집니다.",
        ],
    }

    OUTPUT_DIR.mkdir(exist_ok=True)
    json_path = OUTPUT_DIR / "kpi_results.json"
    md_path = OUTPUT_DIR / "kpi_summary.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = [
        "# Code Shepherd M2 자동 KPI 측정 결과", "",
        "## 측정 범위", "",
        "- 테스트 대상: `mixed_case_01` ~ `mixed_case_06`", 
        "- 정답: 21개 취약점 유형 라벨", 
        "- 비교 단위: 케이스 × 취약점 유형 (총 36개 라벨: 양성 21개, 음성 15개)",
        "- 분석 경로: M2 `analyze(..., 'security_scan')` 직접 실행 (DB/UI 경유하지 않음)",
        "",
        "## 측정 수치", "",
        f"- 정답 일치(TP): **{tp}**", f"- 미탐(FN): **{fn}**",
        f"- 정답에 없는 유형 경고(FP, 잠정): **{fp}**", f"- 정상 유형 미탐지(TN, 잠정): **{tn}**",
        f"- 유형별 재현율(Recall): **{metrics['recall_pct']}%**",
        f"- 유형별 정밀도(잠정): **{metrics['precision_pct_provisional']}%**",
        f"- 유형별 오탐률(잠정): **{metrics['false_positive_rate_pct_provisional']}%**",
        f"- 케이스당 평균 자동 분석 시간: **{metrics['avg_scan_seconds']}초**",
        f"- 미분류 분석 경고: **{uncategorized}건**", "",
        "## 케이스별 결과", "",
        "| 케이스 | 정답 | 일치 | 미탐 | 추가 유형 경고 | 분석시간(초) |", 
        "|---|---:|---:|---:|---:|---:|",
    ]
    for c in detail:
        summary.append(
            f"| {c['case']} | {len(c['expected_types'])} | {len(c['matched'])} | "
            f"{len(c['missed'])} | {len(c['unexpected_type_alerts'])} | {c['analysis_ms']/1000:.2f} |"
        )
    summary += ["", "## 해석 시 주의사항", ""]
    summary += [f"- {w}" for w in result["warnings"]]
    md_path.write_text("\n".join(summary) + "\n", encoding="utf-8")

    print("\n=== 최종 KPI (유형 단위 / 잠정) ===")
    print(f"재현율: {metrics['recall_pct']}% (TP={tp}, FN={fn})")
    print(f"정밀도: {metrics['precision_pct_provisional']}% (잠정; 추가 경고 수동 검증 필요)")
    print(f"오탐률: {metrics['false_positive_rate_pct_provisional']}% (잠정; 정답 라벨 완전성 가정)")
    print(f"케이스당 평균 분석시간: {metrics['avg_scan_seconds']}초")
    print(f"분류되지 않은 규칙 결과: {uncategorized}건")
    print(f"저장: {md_path}")
    print(f"상세: {json_path}")


if __name__ == "__main__":
    main()
