# mixed_case_04

## Purpose

This case validates multi-issue detection for the Task-Link M2 security review agent.
`vulnerable.py` contains **3 different M2 security vulnerabilities in one file**,
exercising the agent's ability to report multiple distinct issues in a single pass.

## Expected Issues

| Rule ID | Title                            | Severity | Line |
|---------|----------------------------------|----------|------|
| SEC-006 | Hardcoded Secrets in Source Code | Critical | 5    |
| SEC-003 | Path Traversal via filename      | High     | 10   |
| SEC-004 | Command Injection via os.system  | Critical | 14   |

- Module: M2
- Source: Task-Link Custom

## Files

- `vulnerable.py`: target source code containing 3 mixed security vulnerabilities
- `expected_issue.json`: expected M2 output for this case

## Notes

This dataset is for evaluation only and must not be used as production service code.
