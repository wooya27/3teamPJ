# mixed_case_03

## Purpose

This case validates multi-issue detection for the Task-Link M2 security review agent.
`vulnerable.py` contains **4 different M2 security vulnerabilities in one file**,
exercising the agent's ability to report multiple distinct issues in a single pass.

## Expected Issues

| Rule ID  | Title                              | Severity | Line |
|----------|------------------------------------|----------|------|
| SEC-006  | Hardcoded Secrets in Source Code   | Critical | 4    |
| SEC-001  | SQL Injection via f-string         | Critical | 24   |
| SEC-005  | Insecure Password Hashing (MD5)    | High     | 28   |
| AUTH-001 | Missing Authorization Check        | High     | 33   |

- Module: M2
- Source: Task-Link Custom

## Files

- `vulnerable.py`: target source code containing 4 mixed security vulnerabilities
- `expected_issue.json`: expected M2 output for this case

## Notes

This dataset is for evaluation only and must not be used as production service code.
