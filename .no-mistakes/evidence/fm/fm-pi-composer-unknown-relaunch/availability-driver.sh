#!/usr/bin/env bash
set -eu
ROOT=$PWD
REAL_TMUX=$(command -v tmux)
REAL_PI=$(command -v pi)
mkdir -p "$ROOT/.live-test-step/no-pi-bin" "$ROOT/.live-test-step/no-tmux-bin"
ln -sf "$REAL_TMUX" "$ROOT/.live-test-step/no-pi-bin/tmux"
ln -sf "$REAL_PI" "$ROOT/.live-test-step/no-tmux-bin/pi"
check() {
  local label=$1 path=$2 want=$3 expected_text=$4 rc=0 out
  shift 4
  printf '\n%s\nPATH=%s\n' "$label" "$path"
  out=$(env -i HOME="$ROOT/.live-test-step/ambient-home" PI_CODING_AGENT_DIR="$ROOT/.live-test-step/ambient-pi" TMPDIR="$ROOT/.live-test-step/tmp" PATH="$path" FM_TEST_SKIP_ORPHAN_REAP=1 "$@" /bin/bash "$ROOT/tests/fm-composer-pi-idle-live-e2e.test.sh" 2>&1) || rc=$?
  printf '%s\nexit=%s\n' "$out" "$rc"
  [ "$rc" = "$want" ]
  case "$out" in *"$expected_text"*) ;; *) exit 1 ;; esac
}
check 'tmux installed, neither Pi executable available: capability skip' "$ROOT/.live-test-step/no-pi-bin:/usr/bin:/bin" 0 'skip: live: pi-signed absent'
check 'Neither Pi executable available, explicitly forced: hard failure' "$ROOT/.live-test-step/no-pi-bin:/usr/bin:/bin" 1 'was requested but pi-signed is not installed' FM_COMPOSER_PI_IDLE_LIVE=1
check 'Neither Pi executable available, family forced: hard failure' "$ROOT/.live-test-step/no-pi-bin:/usr/bin:/bin" 1 'was requested but pi-signed is not installed' FM_LIVE=1
check 'Pi installed, tmux unavailable: capability skip' "$ROOT/.live-test-step/no-tmux-bin:/usr/bin:/bin" 0 'skip: live: tmux absent'
check 'Pi installed, tmux unavailable, forced: hard failure' "$ROOT/.live-test-step/no-tmux-bin:/usr/bin:/bin" 1 'was requested but tmux is not installed' FM_COMPOSER_PI_IDLE_LIVE=1
check 'Explicit guard opt-out wins over family opt-in' "$ROOT/.live-test-step/no-pi-bin:/usr/bin:/bin" 0 'disabled by FM_COMPOSER_PI_IDLE_LIVE=0' FM_COMPOSER_PI_IDLE_LIVE=0 FM_LIVE=1
check 'Family opt-out prevents any harness launch' "$ROOT/.live-test-step/no-tmux-bin:/usr/bin:/bin" 0 'disabled by FM_LIVE=0' FM_LIVE=0
