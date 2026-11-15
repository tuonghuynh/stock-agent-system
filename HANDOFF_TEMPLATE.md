# Worker Handoff Template

Every worker returns this information. Compilation alone is not completion.

```text
Task ID:
Worker:
Branch:
Worktree:
Base commit:
Final commit SHA(s):
Contract version:

Requirements implemented:
-

Acceptance tests addressed:
-

Files changed:
-

Behavior implemented:
-

Validation commands and results:
- Command:
  Result:

Shared contract or migration changes requested:
- None / details

Known limitations or follow-up work:
-

Risks discovered:
-

Security confirmation:
- No secrets added to source, prompts, logs or tests.
- No live-trading capability enabled.
- No deterministic policy or risk gate weakened.
- No files outside assigned ownership changed.

Recommended integration order or dependencies:
-
```

The lead independently inspects changed paths and reruns relevant tests. Only then may the task become `VALIDATED`.
