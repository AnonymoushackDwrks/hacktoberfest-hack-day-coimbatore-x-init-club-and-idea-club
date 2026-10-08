# Demo Repository: Math Service Benchmark

This directory is an autonomous test benchmark for **OctoGemma**.

## Contents
- `math_service.py`: Contains calculation functions with deliberate mathematical and boundary bugs (division by zero, percentage discount calculation formula, and unsorted median computation).
- `test_math_service.py`: Pytest test suite covering all cases.

## Testing Autonomous Self-Healing
You can run OctoGemma against this directory using either interface:

### Web Studio:
Click the quick benchmark chip: **"🛠️ Fix Math Service & Pass Tests"** and hit **Launch Autonomous Agent**.

### CLI:
```bash
python run_cli.py run "Inspect examples/demo_repo/math_service.py and its test file examples/demo_repo/test_math_service.py. Run pytest to find the failures, fix the mathematical logic and edge cases in math_service.py, re-run pytest to verify all tests pass, and report completion."
```
