---
name: code-review
description: Reviews code changes for correctness, safety scope, holdout isolation, determinism, and simplicity before each commit. Use before committing, when asked to review code, check changes, or find bugs.
---

# Code Review

Run this on the changes of every task before committing.

## Process
1. List the changed files.
2. Run the tests and the linter (ruff if present). Report failures first.
3. Check the list below and report findings as High, Medium, or Low, each with file and line.
4. Fix all High findings before the commit. Ask me about Medium and Low ones.

## Checklist
- Correctness: does it do what the task in `task.md` says? Edge cases like empty input and errors?
- Holdout isolation: does any holdout attack, result, or hash reach the defender or a prompt?
- Canary safety: is any canary value printed to logs, shown to the defender, or hardcoded outside `targets/`?
- Determinism: does the judge call a model or use randomness? It must not.
- Secrets: any key, token, or `.env` content in code or files to be committed?
- Scope: does any code attack something outside our local sandbox?
- Tests: does every new behavior have an offline test?
- Simplicity: unused code, extra abstractions, copy-pasted logic between CLI and API?
- Docs: does `project.md` still match the real tree? Does the README still match reality?

## Rules
- Review only what changed. Don't rewrite unrelated code.
- Don't mark something fixed without re-running the tests.

## Working style
- If a finding is a judgment call, ask me instead of deciding. Don't assume.