# Codex Review Loop Protocol

## Purpose

Use a newly launched reviewer agent only as a reviewer. The primary Codex keeps responsibility for implementation decisions, code or plan changes, verification, and final reporting.

The reviewer agent is a helper, not an implementer.

## Roles

### Primary Codex

- Reads this protocol before starting a review loop.
- Uses compact mode by default.
- Gives the reviewer only scoped diff or plan context needed for review.
- Reads the reviewer output and classifies each finding.
- Applies only findings judged valid and in scope.
- Runs the smallest useful verification.
- Reports compactly to the user.

### Reviewer Agent

- Reviews only the current scope provided by the primary Codex.
- Does not modify files.
- Does not run broad refactors.
- Focuses on correctness, regressions, edge cases, missing tests, and mismatches with the stated task.
- Ignores style-only preferences, unrelated existing issues, and broad architectural suggestions unless they directly affect correctness.
- Returns compact findings only.

## Reviewer Selection

Default reviewer:

- `codex`: run a newly launched Codex reviewer.

Available reviewers:

- `codex`: run a newly launched Codex reviewer.
- `agy`: run Antigravity through `/Users/moonkong/.local/bin/agy --sandbox --print` in plan mode.

Default compact shortcuts:

- `code-review-loop [N] [scope]`: use the default `codex` reviewer.
- `agy-code-review-loop [N] [scope]`: use the `agy` reviewer.
- `codex-code-review-loop [N] [scope]`: explicitly use the `codex` reviewer.
- `plan-review-loop [N] [plan]`: use the default `codex` reviewer.
- `agy-plan-review-loop [N] [plan]`: use the `agy` reviewer.
- `codex-plan-review-loop [N] [plan]`: explicitly use the `codex` reviewer.

Audit shortcuts prepend `audit-` after an optional reviewer name, for example `agy-audit-code-review-loop` and `codex-audit-plan-review-loop`. Audit mode preserves review artifacts.

Do not use `agy --dangerously-skip-permissions` for review loops unless the user explicitly asks for it.

## Shortcut Parsing

- Default loop count: 1.
- If the first argument is a natural number, use it as the loop count.
- If the first argument is not a natural number, treat it as the scope or plan and use 1 loop.
- If scope is omitted for a code review, use the current git diff.
- If scope is provided, review only that scoped diff or file set.
- If plan is omitted for a plan review, use the pasted plan text when available.

Examples:

- `agy-code-review-loop`: 1 loop, current git diff.
- `agy-code-review-loop app/api/entries.py`: 1 loop, scoped to that path.
- `agy-code-review-loop 2`: 2 loops, current git diff.
- `agy-code-review-loop 2 app/api/entries.py`: 2 loops, scoped to that path.
- `agy-plan-review-loop docs/plan.md`: 1 loop, scoped to that plan file.

## Invocation Policy

Read and apply this protocol only when the user explicitly asks for a review loop or uses one of the shortcuts. Do not apply it to unrelated implementation, debugging, explanation, or commit requests.

### Compact Mode

Compact mode is the default for all non-audit shortcuts:

- Review code diffs or plans, as requested.
- Apply valid findings to code, or to the plan only for plan reviews.
- Run relevant verification.
- Do not commit unless the user explicitly asks.
- Do not preserve review artifacts by default.

Compact limits:

- Task context: at most 5 bullets.
- Implemented changes: at most 7 bullets.
- Design constraints: at most 5 bullets.
- Reviewer output: at most 3 actionable findings.
- No praise, broad summary, or task restatement.
- If nothing should change, the reviewer must return exactly: `No actionable findings.`

Do not create `codex_reviews/` files in compact mode. If a temporary prompt file is necessary, keep it compact, store it outside the repository when practical, and remove it after the review.

For compact `agy` reviews, pass the prompt directly as the `--print` argument. Do not wrap `agy` in `/bin/zsh -lc`, use `$(cat ...)`, or redirect its output. Read the command output directly.

### Audit Mode

Use audit mode only when the user uses an `audit-*` shortcut. Preserve:

- `codex_reviews/loop_N_prompt.md`
- `codex_reviews/loop_N_review.md`
- `codex_reviews/loop_N_decision.md`
- `codex_reviews/loop_N_verification.txt`
- `codex_reviews/summary.md`

Audit mode permits at most 5 actionable findings. Do not include `codex_reviews/` in commits unless the user explicitly asks.

## Primary Codex Loop Steps

1. Determine the loop count and review scope.
2. Inspect only the scoped diff and minimal relevant context.
3. Prepare a compact reviewer prompt.
4. Run the selected reviewer.
5. Read and classify findings as accepted, rejected, or needs-user-decision.
6. Stop early if the reviewer returns `No actionable findings.`
7. Apply only accepted findings.
8. Run the smallest useful verification.
9. Repeat only when accepted changes require another requested loop.
10. Report compactly to the user.

Plan reviews may update only the plan. They must not modify implementation code.

## Reviewer Commands

Codex reviewer in audit mode:

```sh
codex exec --ephemeral -s read-only -C /Users/moonkong/dev/lifhop -o codex_reviews/loop_N_review.md - < codex_reviews/loop_N_prompt.md
```

Antigravity reviewer (always use plan mode so repository instructions cannot turn review into implementation work):

```sh
/Users/moonkong/.local/bin/agy --sandbox --print '<review_prompt>' --mode plan --print-timeout 10m --log-file /private/tmp/agy-review.log
```

Run the `agy` command with escalated host permissions from the first attempt because normal CLI startup needs to create its log and bind a localhost language-server port. Request reusable approval scoped to this fixed prefix:

```text
["/Users/moonkong/.local/bin/agy", "--sandbox", "--print"]
```

Keep `--sandbox` and `--mode plan` enabled so the reviewer remains read-only. Never use `--dangerously-skip-permissions` unless the user explicitly requests it.

Capture reviewer output directly from the command result. In audit mode, write the captured output to `codex_reviews/loop_N_review.md` after the command completes. Keep the executable path, option order, and log path stable so reusable approval continues to match.

## Reviewer Prompt Template

```text
Review only the provided diff and compact context.

You are a reviewer only. Do not modify files.

Task context:
{task_context_max_5_bullets}

Implemented changes:
{implemented_changes_max_7_bullets}

Design intent and constraints:
{design_constraints_max_5_bullets}

Review focus:
- correctness bugs
- behavioral regressions
- edge cases
- missing or broken tests
- mismatches with the stated task context

Do not focus on:
- broad refactors
- style-only preferences
- unrelated existing issues
- changes outside the provided diff or scope

Return:
- at most 3 actionable findings
- no praise
- no general summary
- no restatement of the task
- each finding should be concise
- each finding should include severity, file/line when possible, issue, and suggested fix
- if nothing should change, return exactly: No actionable findings.

Do not inspect unrelated files unless a finding cannot be validated without them.
```

In audit mode, the prompt may request at most 5 actionable findings.

## Audit Decision Log Template

Use this format only for `codex_reviews/loop_N_decision.md`:

```markdown
# Review Loop N Decision Log

## Summary
- Findings reported: 0
- Accepted: 0
- Rejected: 0
- Needs user decision: 0

## Finding 1
Status: accepted | rejected | needs-user-decision
Reviewer severity: high | medium | low | unspecified

Reviewer claim:
- ...

Primary Codex decision:
- ...

Changes made:
- ...

Verification:
- ...
```

## Verification Guidance

Run the smallest useful verification set for the actual change. Prefer formatting and analyzing changed files, targeted tests for touched behavior, and broader tests only when risk or the user request justifies them.

If verification fails for an unrelated existing issue, record the command, failure summary, why it appears unrelated, and whether changed files were verified separately.

## Stop Conditions

Stop the loop early when:

- The requested loop count is reached.
- The reviewer returns `No actionable findings.`
- No accepted findings are found.
- Accepted findings do not cause code or plan changes.
- A finding requires a product, UX, or scope decision from the user.
- Verification fails in a way that blocks safe continuation.
- The reviewer repeats the same rejected finding.
- The reviewer attempts to act as an implementer.

## Judgment Policy

- Do not let reviewer output override primary Codex judgment.
- Do not apply suggestions that conflict with user instructions.
- Do not apply suggestions outside the requested scope.

## User-Facing Report

Keep each section short:

```markdown
Reviewer:
Loops completed:
Findings:
Accepted changes:
Rejected findings:
Needs user decision:
Verification:
Notes:
```

For audit mode, also mention preserved artifacts under `codex_reviews/`.
