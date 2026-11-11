# insecure_password_hash_case

## Purpose

This case validates `SEC-005` detection for the Task-Link M2 security review agent.

## Expected Issue

- Rule ID: `SEC-005`
- Severity: `High`
- Module: M2
- Source: Task-Link Custom

## Files

- `vulnerable.py`: target source code using MD5 for password hashing
- `fixed.py`: corrected version using bcrypt
- `expected_issue.json`: expected M2 output for this case

## Notes

This dataset is for evaluation only and must not be used as production service code.
