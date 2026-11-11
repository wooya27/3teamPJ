# mixed_case_06

## Purpose

This case validates multi-issue detection for the Task-Link M2 security review agent.
`vulnerable.py` contains **5 different M2 security vulnerabilities in one file**,
exercising the agent's ability to report multiple distinct issues in a single pass.

## Expected Issues

| Rule ID  | Title                              | Severity | Line |
|----------|------------------------------------|----------|------|
| SEC-006  | Hardcoded Secrets in Source Code   | Critical | 5    |
| SEC-001  | SQL Injection via f-string         | Critical | 24   |
| SEC-003  | Path Traversal via filename        | High     | 29   |
| SEC-005  | Insecure Password Hashing (MD5)    | High     | 32   |
| AUTH-001 | Missing Authorization Check        | High     | 37   |

- Module: M2
- Source: Task-Link Custom

## Files

- `vulnerable.py`: target source code containing 5 mixed security vulnerabilities
- `expected_issue.json`: expected M2 output for this case

## Notes

This dataset is for evaluation only and must not be used as production service code.
