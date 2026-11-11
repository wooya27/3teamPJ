# command_injection_case

## Purpose

This case validates `SEC-004` detection for the Task-Link M2 security review agent.

## Expected Issue

- Rule ID: `SEC-004`
- Severity: `Critical`
- Module: M2
- Source: Task-Link Custom

## Files

- `vulnerable.py`: target source code with command injection vulnerability
- `fixed.py`: corrected version using subprocess with argument list
- `expected_issue.json`: expected M2 output for this case

## Notes

This dataset is for evaluation only and must not be used as production service code.
