# Required-check fallback validation

## Result

Live refusal/configuration diagnostics and focused behavioral checks passed. Full live merge validation remains incomplete: no disposable GitHub PR/repository or authority to publish fixture statuses, alter protection, push, or merge was supplied. All live product invocations used independently verified, already-merged incident PRs, preserving a separate closed-state safety guard. No production merge, status publication, credential change, or fleet operation was performed.

## Live evidence

`live-merge-refusals.log` contains real authenticated `gh` responses and actual `bin/fm-pr-merge.sh` output, without forge mocks:

- https://github.com/maiarowsky/fortnight/pull/745: `validate` succeeded; the Mac status was absent at `ae1e2cfdcafd963eb23e0b306ae219920fd0e3b2`.
- https://github.com/maiarowsky/fortnight/pull/746: `validate` succeeded; the Mac status was absent at `7951fbaef734d23ecea14e479a062e155e04318c`.
- https://github.com/maiarowsky/fortnight/pull/748: `validate` succeeded; the Mac status was absent at `6b4954975199f55fe6d299b9e138f9a5d57d2ef3`.
- GitHub returned the actual Free-plan HTTP 403 for branch rules. With both contexts declared, each invocation explicitly named the unreported Mac status at that PR's head. Subsequent GitHub reads confirmed unchanged PR state/head.
- A waiver naming `validate` did not suppress the missing Mac requirement.
- Malformed declarations for a different repository, including a control character, reported the declaration path and line 2 even with named waivers.
- A directory, dangling symlink, and mode-000 declaration file each reported an unreadable declaration rather than silently dropping it.
- An explicit config-directory override correctly selected scoped, uppercase-repository, commented, duplicate `validate` declarations and ignored an invalid declaration file in the non-selected directory.

These are real runtime diagnostics, not proof that an open PR merged or that a missing check was its sole refusal condition. Each live PR also remained refused because it was already merged. CLI transcripts are the end-user evidence; there is no graphical UI surface in this change.

## Focused fixture-backed evidence (not live)

`baseline-regression-cli.log` reproduces the defect using the base revision's executable and the existing forge fixture: a mergeable open PR with only green `validate`, a declared Mac requirement, and a plan-unavailable 403 reached `gh pr merge` and returned success. The focused regression assertion failed as expected before the fix.

`focused-merge-cli.log` records the target executable refusing that same missing status, accepting its green commit-status counterpart, preserving classic/ruleset requirements and producer binding, refusing other forge-read errors, handling exact named missing/red waivers and pending statuses, parsing scoped declarations, and rejecting malformed/unreadable configuration. The selected existing behavioral tests all completed successfully. GitHub and merge outcomes in this file are mocked, never live evidence.

`incident-two-context-cli.log` records additional public-entrypoint cases declaring **both** `validate` and `autofirma/local-mac-gate`: both green reaches the head-bound merge command; either absent refuses; differently cased Mac status refuses; a stale recorded head does not replace the live-head missing-check diagnostic. These cases also use mocked GitHub responses.

Selected existing tests:

- `test_declared_required_check_on_plan_unavailable`
- `test_declared_required_checks_supplement_forge_requirements`
- `test_declared_required_checks_use_existing_waivers`
- `test_declared_required_checks_format_and_config_override`
- `test_declared_required_checks_do_not_weaken_app_binding`
- `test_declared_required_checks_file_states`
- `test_malformed_required_check_declaration_refuses`
- `test_required_partial_reads_report_all_failures`
- `test_allow_missing_follows_the_allow_red_rules`
- `test_required_checks_reported_and_green_merge`

Additional executed case: `test_incident_both_declared_contexts_and_head` in the evidence driver.

## Execution

Drivers and complete outputs are preserved in this evidence directory. Existing tests were selected into `focused-merge-driver.sh` without changing tracked files. Temporary Git fixture repositories and operational homes were placed under the worktree's `.nm-test-step/`; orphan scanning was disabled so tests did not inspect unrelated host fixtures.

Commands used:

```sh
# Base executable was materialized transiently beside its real script dependencies.
git show aedb7bbf3b038672cef8b700df2b65ff4491dbfd:bin/fm-pr-merge.sh > bin/.nm-test-baseline-pr-merge.sh
chmod +x bin/.nm-test-baseline-pr-merge.sh

# Each invocation also cleared inherited FM_CONFIG_OVERRIDE, FM_DATA_OVERRIDE,
# FM_PROJECTS_OVERRIDE, FM_TEST_HOME and FM_TEST_USER_HOME with env -u.
BASELINE=1 FM_TEST_SKIP_ORPHAN_REAP=1 TMPDIR="$PWD/.nm-test-step/tmp" EVIDENCE_TRANSCRIPT="$EVIDENCE/baseline-regression-cli.log" bash "$EVIDENCE/focused-merge-driver.sh"
FM_TEST_SKIP_ORPHAN_REAP=1 TMPDIR="$PWD/.nm-test-step/tmp" EVIDENCE_TRANSCRIPT="$EVIDENCE/focused-merge-cli.log" bash "$EVIDENCE/focused-merge-driver.sh"
ONLY_INCIDENT=1 FM_TEST_SKIP_ORPHAN_REAP=1 TMPDIR="$PWD/.nm-test-step/tmp" EVIDENCE_TRANSCRIPT="$EVIDENCE/incident-two-context-cli.log" bash "$EVIDENCE/focused-merge-driver.sh"
python3 "$EVIDENCE/live-merge-refusal-driver.py"
```

`EVIDENCE` denotes `/Users/jaroslawmacioszek/.no-mistakes/evidence/01M3TS66QGJVKHGKSDGS4H3FD3`. The full repository suite, linters, formatters, and static analysis were not run. All worktree fixtures and the temporary base executable were removed after validation; no source or tracked test changes were made.

## Remaining live evidence

An expressly authorized disposable GitHub fixture is needed to prove open-PR missing/red/pending refusal, exact attended waivers, successful merging with both contexts green on the exact head, and an adversarial producer-binding case. This requires permission to create/push fixture commits and PRs, publish statuses/check runs, configure protection where supported, and merge the disposable PRs, with an explicit exception to the current no-outside-worktree-mutation boundary. Existing production authentication is available; the blocker is mutation authority, not a missing CLI or login.
