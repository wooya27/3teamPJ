# auth_missing_case

## Purpose

This case validates `AUTH-001` detection for the Task-Link M2 security review agent.

## Expected Issue

- Rule ID: `AUTH-001`
- Severity: `High`
- Module: M2
- Source: Task-Link Custom

## Files

- `vulnerable.py`: target source code with missing authorization check
- `fixed.py`: corrected version with ownership and admin validation
- `expected_issue.json`: expected M2 output for this case

## Notes

This dataset is for evaluation only and must not be used as production service code.
