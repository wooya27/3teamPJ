from app import analyzer


CASES = [
    # 경로 탐색: 4개
    ("PT01", "_scan_path_traversal",
     "file_path = BASE_DIR / filename", True),

    ("PT02", "_scan_path_traversal",
     "file_path = BASE_DIR/filename", True),

    ("PT03", "_scan_path_traversal",
     "print('hello')", False),

    ("PT04", "_scan_path_traversal",
     "message = 'BASE_DIR / filename'", False),

    # 인가 누락: 4개
    ("AUTH01", "_scan_missing_auth",
     "def delete_user(target_user_id):\n"
     "    del users[target_user_id]", True),

    ("AUTH02", "_scan_missing_auth",
     "def delete_user(target_user_id):\n"
     "    if target_user_id in users:\n"
     "        del users[target_user_id]", True),

    ("AUTH03", "_scan_missing_auth",
     "def delete_user(current_user_id, target_user_id):\n"
     "    if current_user_id == target_user_id:\n"
     "        del users[target_user_id]", False),

    ("AUTH04", "_scan_missing_auth",
     "def clear_cache():\n"
     "    del temp_cache['old']", False),

    # 하드코딩 비밀정보: 4개
    ("SECRET01", "_scan_hardcoded_secret",
     'API_KEY = "fake-demo-key"', True),

    ("SECRET02", "_scan_hardcoded_secret",
     'SERVICE_API_KEY = "fake-demo-key"', True),

    ("SECRET03", "_scan_hardcoded_secret",
     'import os\nAPI_KEY = os.getenv("API_KEY")', False),

    ("SECRET04", "_scan_hardcoded_secret",
    'PASSWORD = None', False),
]


def test_scanner_evaluation(tmp_path):
    correct = 0

    for index, (name, scanner_name, code, expected) in enumerate(CASES):
        file = tmp_path / f"case_{index}.py"
        file.write_text(code, encoding="utf-8")

        scanner = getattr(analyzer, scanner_name)

        issues = scanner(
            [file.name],
            str(tmp_path)
        )

        detected = len(issues) > 0
        matched = detected == expected

        if matched:
            correct += 1

        print(
            f"{name}: "
            f"예상={expected}, "
            f"실제={detected}, "
            f"일치={matched}"
        )

    print(f"\n평가 결과: {correct}/{len(CASES)}")