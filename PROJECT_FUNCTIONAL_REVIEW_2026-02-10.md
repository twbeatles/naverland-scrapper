# Functional Implementation Risk Review (2026-02-10)

## Scope
- Reviewed documents: CLAUDE.md, README.md
- Reviewed code: src/main.py, src/core/*, src/ui/*, src/utils/paths.py, tests/test_item_parser.py
- Validation commands: python -m compileall src, python tests/test_item_parser.py

## Critical Issues
1. Merge conflict markers remain in 14 runtime Python files.
- Evidence: markers `<<<<<<<`, `=======`, `>>>>>>>` found in main/core/ui files.
- Impact: application is currently non-runnable.
- Verification: `python -m compileall src` fails with SyntaxError in multiple files.

2. `src/utils/paths.py` is structurally broken.
- Evidence: duplicated blocks and remaining conflict artifact.
- Impact: startup path/bootstrap reliability is at risk.

## High Priority Risks
1. README entrypoint mismatch.
- README command points to `부동산 매물 크롤러 v10.0 claude.py`, but file does not exist.
- Current architecture entrypoint is `src/main.py`.

2. Python version policy mismatch.
- CLAUDE.md says Python 3.9+.
- README.md says Python 3.8+.

3. No automated guard against syntax/conflict regressions.

## Recommended Additions
1. Add CI gate: syntax check + tests on every PR.
2. Add dependency lock file (`requirements.txt` or equivalent).
3. Expand tests to DB migration, parser, settings/cache persistence.
4. Add startup preflight checks for dependency and environment integrity.

## Command Snapshot
- `python -m compileall src`: FAIL (syntax errors from merge markers).
- `python tests/test_item_parser.py`: PASS (2 tests).

## Suggested Order
1. Resolve all merge conflicts in affected files.
2. Re-run compileall until clean.
3. Align README run command and Python version policy.
4. Add CI and broaden tests.

## Bottom Line
The top blocker is source integrity, not feature depth: unresolved merge conflicts currently prevent normal execution. Stabilize codebase integrity first, then improve docs and automation guardrails.
