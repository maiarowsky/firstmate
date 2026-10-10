#!/usr/bin/env bash
set -eu
ROOT=$PWD
EVIDENCE=/Users/jaroslawmacioszek/.no-mistakes/evidence/01M4K30EK3AB66P87XY0KKNBAV
REAL_TMUX=$(command -v tmux)
REAL_PI=$(command -v pi)
LAB=$(mktemp -d "$ROOT/.live-test-step/fm-lab.XXXXXX")
"$ROOT/bin/fm-lab-home.sh" create "$LAB" >/dev/null
SOCKET_DIR=$("$ROOT/bin/fm-lab-home.sh" tmux-dir "$LAB")
cleanup() {
  local rc=$?
  trap - EXIT
  TMUX_TMPDIR="$SOCKET_DIR" "$REAL_TMUX" -L fm-lab kill-server 2>/dev/null || true
  "$ROOT/bin/fm-lab-home.sh" teardown "$LAB" || rc=1
  rm -rf "$LAB"
  printf 'Disposable Pi worker and private tmux server removed.\n'
  exit "$rc"
}
trap cleanup EXIT
mkdir -p "$LAB/agent" "$LAB/cwd" "$LAB/shim"
printf '%s\n' '{"openai-codex":{"type":"oauth","access":"fixture-unused","refresh":"fixture-unused","expires":4102444800000}}' > "$LAB/agent/auth.json"
printf '#!/usr/bin/env bash\nexec env TMUX_TMPDIR=%q %q -L fm-lab "$@"\n' "$SOCKET_DIR" "$REAL_TMUX" > "$LAB/shim/tmux"
chmod +x "$LAB/shim/tmux"
export PATH="$LAB/shim:$PATH" HOME="$LAB" PI_CODING_AGENT_DIR="$LAB/agent" FM_HOME="$LAB"
unset HERDR_ENV HERDR_SOCKET_PATH HERDR_PANE_ID HERDR_TAB_ID HERDR_WORKSPACE_ID HERDR_SESSION
unset FM_GATE_REFUSE_BYPASS FM_ROOT_OVERRIDE FM_STATE_OVERRIDE FM_DATA_OVERRIDE FM_CONFIG_OVERRIDE FM_PROJECTS_OVERRIDE
. "$ROOT/bin/fm-tmux-lib.sh"
. "$ROOT/bin/fm-backend.sh"
# No user shell or tmux configuration is loaded. A shell preserves the worker's
# endpoint after the actual Pi process handles /quit.
tmux -f /dev/null new-session -d -s proof -n fm-pi-proof -x 160 -y 40 -c "$LAB/cwd" -- /bin/bash --noprofile --norc -i
printf -v launch '%q ' env -u NO_MISTAKES_GATE -u FM_GATE_REFUSE_BYPASS HOME="$LAB" PI_CODING_AGENT_DIR="$LAB/agent" "$REAL_PI" --provider openai-codex --model gpt-6.1-sol --thinking xhigh --offline --no-session --no-extensions --no-skills --no-prompt-templates --no-themes --tui-mode regular --approve
tmux send-keys -t proof:fm-pi-proof -l "$launch"
tmux send-keys -t proof:fm-pi-proof Enter
for ((i=0; i<150; i++)); do
  [ "$(fm_tmux_composer_state proof:fm-pi-proof)" != empty ] || break
  sleep 0.1
done
[ "$i" -lt 150 ]
cat > "$LAB/state/pi-proof.meta" <<EOF
window=proof:fm-pi-proof
endpoint_task_id=pi-proof
worktree=$LAB/cwd
project=$LAB/cwd
harness=pi
kind=secondmate
backend=tmux
model=openai-codex/gpt-6.1-sol
effort=xhigh
EOF
cp "$LAB/state/pi-proof.meta" "$LAB/pi-proof.meta.before"
capture() {
  tmux capture-pane -e -p -t proof:fm-pi-proof > "$EVIDENCE/control-$1.ansi"
}
control() {
  env FM_CONTROL_POLL=0.2 FM_CONTROL_SETTLE_WAIT=1 FM_CONTROL_EXIT_WAIT=15 "$ROOT/bin/fm-control.sh" pi-proof "$@"
}
printf 'Real Pi profile: openai-codex/gpt-6.1-sol xhigh; offline, no submitted model prompt.\n'
printf 'Initial worker: identity=%s composer=%s agent=%s\n' "$(fm_tmux_composer_identity proof:fm-pi-proof)" "$(fm_tmux_composer_state proof:fm-pi-proof)" "$(fm_backend_agent_state tmux proof:fm-pi-proof)"
capture idle
n=0
for draft in 'draft-not-submitted' '❯' '$0.000 (sub)' 'Type a message...'; do
  n=$((n+1))
  tmux send-keys -t proof:fm-pi-proof -l "$draft"
  for ((i=0; i<100; i++)); do
    [ "$(fm_tmux_composer_state proof:fm-pi-proof)" != pending ] || break
    sleep 0.1
  done
  [ "$i" -lt 100 ]
  before=$(tmux capture-pane -p -t proof:fm-pi-proof)
  printf '\nDraft %s: %s\n' "$n" "$draft"
  printf 'Before exit: composer=%s\n' "$(fm_tmux_composer_state proof:fm-pi-proof)"
  rc=0
  out=$(control exit 2>&1) || rc=$?
  printf 'fm-control exit rc=%s: %s\n' "$rc" "$out"
  [ "$rc" = 1 ]
  case "$out" in *'composer visibly holds pending text'*'refusing to type the /quit'*) ;; *) exit 1 ;; esac
  after=$(tmux capture-pane -p -t proof:fm-pi-proof)
  [ "$before" = "$after" ]
  [ "$(fm_backend_agent_state tmux proof:fm-pi-proof)" = alive ]
  capture "draft-$n-preserved"
  printf 'Actual viewport unchanged; Pi still alive; no /quit appended.\n'
  tmux send-keys -t proof:fm-pi-proof C-u
  for ((i=0; i<100; i++)); do
    [ "$(fm_tmux_composer_state proof:fm-pi-proof)" != empty ] || break
    sleep 0.1
  done
  [ "$i" -lt 100 ]
  printf 'After Ctrl+U: composer=%s\n' "$(fm_tmux_composer_state proof:fm-pi-proof)"
done
printf '\nIdle interrupt followed by exit:\n'
control interrupt
[ "$(fm_tmux_composer_state proof:fm-pi-proof)" = empty ]
capture idle-after-interrupt
control exit
[ "$(fm_backend_agent_state tmux proof:fm-pi-proof)" = dead ]
tmux has-session -t proof
capture stopped-shell
printf 'Postcondition: Pi agent dead; exact endpoint still exists; metadata unchanged.\n'
cmp -s "$LAB/state/pi-proof.meta" "$LAB/pi-proof.meta.before"
control exit
