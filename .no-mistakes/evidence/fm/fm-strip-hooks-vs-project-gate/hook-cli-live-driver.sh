#!/usr/bin/env bash
set -euo pipefail
ROOT=$PWD
TMP_ROOT="$ROOT/.validation-temp/cli-live"
EVIDENCE=/Users/jaroslawmacioszek/.no-mistakes/evidence/01M45B82ANJF07B6F1VXXV80JH
STRIP="$ROOT/bin/fm-git-strip-ai-trailers.sh"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 TMPDIR="$ROOT/.validation-temp"
unset GIT_CONFIG_COUNT GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0 GIT_CONFIG_PARAMETERS
export GIT_AUTHOR_NAME='Live Hook Fixture' GIT_COMMITTER_NAME='Live Hook Fixture'
export GIT_AUTHOR_EMAIL=hook-fixture@example.invalid GIT_COMMITTER_EMAIL=hook-fixture@example.invalid
cleanup() {
  [ ! -d "$TMP_ROOT" ] || find "$TMP_ROOT" -type d -exec chmod u+rwx {} +
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT
mkdir -p "$TMP_ROOT"
make_repo() {
  mkdir -p "$1"
  git -C "$1" init -q -b main
  printf 'fixture\n' > "$1/README"
  git -C "$1" add README
  git -C "$1" commit -qm initial
}
write_hooks() {
  local repo=$1 hooks=$2
  mkdir -p "$hooks"
  printf '#!/bin/sh\n./health-check || exit $?\nprintf "pre-commit\\n" >> hook-order\n' > "$hooks/pre-commit"
  printf '#!/bin/sh\nprintf "prepare-commit-msg\\n" >> hook-order\nprintf "\\nCo-Authored-By: Claude <noreply@anthropic.com>\\n" >> "$1"\n' > "$hooks/prepare-commit-msg"
  printf '#!/bin/sh\nprintf "commit-msg\\n" >> hook-order\ncp "$1" project-message\n' > "$hooks/commit-msg"
  printf '#!/bin/sh\nprintf "post-commit\\n" >> hook-order\n' > "$hooks/post-commit"
  chmod +x "$hooks/"{pre-commit,prepare-commit-msg,commit-msg,post-commit}
  printf '#!/bin/sh\nset -eu\nactual=$(git rev-parse --path-format=absolute --git-path hooks/pre-commit)\nprintf "effective pre-commit: %%s\\n" "$actual"\n[ -x "$actual" ] && [ "$actual" = "$EXPECTED_PRE_COMMIT" ] || { echo "effective Git pre-commit is non-executable or not the canonical guard"; exit 42; }\n' > "$repo/health-check"
  chmod +x "$repo/health-check"
}

# Reproduce the reported guard failure through the previous executable interface, not a source assertion.
git show f470a01c098c1536d83b802874bd954a2c04b506:bin/fm-git-strip-ai-trailers.sh > "$TMP_ROOT/baseline-strip.sh"
chmod +x "$TMP_ROOT/baseline-strip.sh"
repo="$TMP_ROOT/baseline"
make_repo "$repo"
write_hooks "$repo" "$repo/.git/hooks"
export EXPECTED_PRE_COMMIT="$repo/.git/hooks/pre-commit"
"$TMP_ROOT/baseline-strip.sh" install "$TMP_ROOT/baseline-wrappers" "$repo"
echo '=== Baseline reproduction: ordinary canonical-hook health check with the old launch environment ==='
set +e
(cd "$repo" && export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0="$TMP_ROOT/baseline-wrappers"; ./health-check)
rc=$?
set -e
[ "$rc" = 42 ]
echo "baseline health-check exit: $rc"

for variant in default relative absolute late; do
  repo="$TMP_ROOT/$variant"
  make_repo "$repo"
  case "$variant" in
    default) hooks="$repo/.git/hooks" ;;
    relative|late) hooks="$repo/project-hooks"; git -C "$repo" config core.hooksPath project-hooks ;;
    absolute) hooks="$TMP_ROOT/absolute-hooks"; git -C "$repo" config core.hooksPath "$hooks" ;;
  esac
  [ "$variant" = late ] || write_hooks "$repo" "$hooks"
  launch=$("$STRIP" launch-env "$TMP_ROOT/$variant-wrappers" "$repo")
  [ "$variant" != late ] || write_hooks "$repo" "$hooks"
  export EXPECTED_PRE_COMMIT="$hooks/pre-commit"
  echo "=== Current product: $variant project hook layout ==="
  (
    cd "$repo"
    eval "$launch"
    ./health-check
    sh -c ./health-check
    git -c 'alias.health=!./health-check' health
    git commit --allow-empty --trailer 'Co-Authored-By: Codex <noreply@openai.com>' --trailer 'Co-Authored-By: Jane Doe <jane@example.com>' -m "fix: live $variant validation"
    echo 'Persisted commit message:'
    body=$(git log -1 --format=%B)
    printf '%s\n' "$body"
    [[ "$body" != *noreply@openai.com* && "$body" != *noreply@anthropic.com* && "$body" == *'Jane Doe <jane@example.com>'* ]]
    [ "$(cat project-message)" = "$body" ]
    [ "$(cat hook-order)" = $'pre-commit\nprepare-commit-msg\ncommit-msg\npost-commit' ]
    echo 'Project commit-msg input equals persisted stripped message; all four hooks ran in order.'
  )
  [ ! -e "$TMP_ROOT/$variant-wrappers" ]
done

repo="$TMP_ROOT/task-repository"
other="$TMP_ROOT/other-repository"
make_repo "$repo"
make_repo "$other"
write_hooks "$repo" "$repo/.git/hooks"
write_hooks "$other" "$other/.git/hooks"
launch=$("$STRIP" launch-env "$TMP_ROOT/cross-repo-wrappers" "$repo")
export EXPECTED_PRE_COMMIT="$other/.git/hooks/pre-commit"
echo '=== Current product: child Git in another repository uses that repository canonical guard ==='
(
  eval "$launch"
  git -C "$other" -c "alias.validate=!./health-check && git commit --allow-empty --trailer 'Co-Authored-By: Cursor <cursoragent@cursor.com>' -m 'fix: another repository'" validate
  [ ! -e "$repo/hook-order" ]
  [ "$(cat "$other/hook-order")" = $'pre-commit\nprepare-commit-msg\ncommit-msg\npost-commit' ]
  body=$(git -C "$other" log -1 --format=%B)
  [[ "$body" != *cursoragent@cursor.com* && "$body" != *noreply@anthropic.com* ]]
  echo "Persisted commit: $body"
  write_hooks "$other" "$other/command-hooks"
  export EXPECTED_PRE_COMMIT="$other/command-hooks/pre-commit"
  git -C "$other" -c core.hooksPath=command-hooks commit --allow-empty --trailer 'Co-Authored-By: Cursor <cursoragent@cursor.com>' -m 'fix: command scoped hooks'
  body=$(git -C "$other" log -1 --format=%B)
  [[ "$body" != *cursoragent@cursor.com* && "$body" != *noreply@anthropic.com* ]]
  echo "Persisted command-scoped commit: $body"
  rm "$other/hook-order"
  git -C "$other" config core.hooksPath ''
  git -C "$other" commit --allow-empty --trailer 'Co-Authored-By: Cursor <cursoragent@cursor.com>' -m 'fix: disabled project hooks'
  [ ! -e "$other/hook-order" ]
  body=$(git -C "$other" log -1 --format=%B)
  [[ "$body" != *cursoragent@cursor.com* ]]
  echo "Persisted disabled-project-hook commit: $body"
  echo 'Command-scoped and disabled project hooks retained their Git semantics while AI stripping remained active.'
)
echo 'All public hook CLI scenarios passed; disposable repositories removed on exit.'
