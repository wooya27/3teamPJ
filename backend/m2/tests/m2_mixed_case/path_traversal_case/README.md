# path_traversal_case

## Purpose

This case validates `SEC-003` detection for the Task-Link M2 security review agent.

## Expected Issue

- Rule ID: `SEC-003`
- Severity: `High`
- Module: M2
- Source: Task-Link Custom

## Files

- `vulnerable.py`: target source code with path traversal vulnerability
- `fixed.py`: corrected version with path validation
- `expected_issue.json`: expected M2 output for this case

## Notes

This dataset is for evaluation only and must not be used as production service code.
