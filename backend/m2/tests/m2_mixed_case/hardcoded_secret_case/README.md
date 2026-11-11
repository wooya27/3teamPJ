# hardcoded_secret_case

## Purpose

This case validates `SEC-006` detection for the Task-Link M2 security review agent.

## Expected Issue

- Rule ID: `SEC-006`
- Severity: `Critical`
- Module: M2
- Source: Task-Link Custom

## Files

- `vulnerable.py`: target source code with hardcoded credentials
- `fixed.py`: corrected version using environment variables
- `expected_issue.json`: expected M2 output for this case

## Notes

This dataset is for evaluation only and must not be used as production service code.
