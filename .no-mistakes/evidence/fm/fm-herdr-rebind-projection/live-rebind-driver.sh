#!/usr/bin/env bash
# Live driver: real herdr lab session, real fm-spawn / fm-control relaunch,
# run from a "firstmate" launcher pane inside the lab, to show where a rebind
# of a proven-gone endpoint lands.
set -u
ROOT=${ROOT:?}
EV=${EV:?}
LOG="$EV/live-rebind-transcript.txt"
: > "$LOG"
say() { printf '%s\n' "$*" | tee -a "$LOG"; }
unset HERDR_ENV HERDR_PANE_ID HERDR_TAB_ID HERDR_WORKSPACE_ID HERDR_SOCKET_PATH HERDR_SESSION
SCR=$(mktemp -d "$(cd "${TMPDIR:-/tmp}" && pwd -P)/fm-rebind-live.XXXXXX")
LAB=$(mktemp -d "$(cd "${TMPDIR:-/tmp}" && pwd -P)/fm-lab.XXXXXX")
"$ROOT/bin/fm-lab-home.sh" create "$LAB" >/dev/null || exit 1
SESSION=$("$ROOT/bin/fm-herdr-lab.sh" name rebind-proj) || exit 1
FAKEBIN="$SCR/fakebin"; mkdir -p "$FAKEBIN" "$SCR/claude-config"
printf '{}\n' > "$SCR/claude-config/.claude.json"
cat > "$FAKEBIN/claude" <<EOF
#!/usr/bin/env bash
case "\${1:-}" in --help|-h|--version|-v) echo "inert test harness"; exit 0 ;; esac
printf '%s\t%s\n' "\$PWD" "\$*" >> "$SCR/claude-launches"
exec sleep 100000
EOF
cp "$FAKEBIN/claude" "$FAKEBIN/pi"
sed -i '' 's/claude-launches/pi-launches/' "$FAKEBIN/pi"
chmod +x "$FAKEBIN/claude" "$FAKEBIN/pi"
LAB_READY=0
WTS=""
cleanup() {
  local wt
  for wt in $WTS; do
    [ -d "$wt" ] && treehouse return --force "$wt" >/dev/null 2>&1
    case "$wt" in "$HOME"/.treehouse/proj-*/*) rm -rf "${wt%/*/*}" ;; esac
  done
  [ "$LAB_READY" = 1 ] && "$ROOT/bin/fm-herdr-lab.sh" teardown "$SESSION" >/dev/null 2>&1
  chmod -R u+w "$SCR" "$LAB" 2>/dev/null
  rm -rf "$SCR" "$LAB"
}
trap cleanup EXIT
lab() { "$ROOT/bin/fm-herdr-lab.sh" run "$SESSION" "$@"; }

PROJ="$SCR/proj"; mkdir -p "$PROJ"
git -C "$PROJ" init -q; printf '# fixture\n' > "$PROJ/README.md"; git -C "$PROJ" add README.md
git -C "$PROJ" -c user.name=t -c user.email=t@example.invalid commit -qm initial
git clone --quiet --bare "$PROJ" "$PROJ.origin.git"; git -C "$PROJ" remote add origin "file://$PROJ.origin.git"
for id in rbp rbo; do
  mkdir -p "$LAB/data/$id"
  printf '# Task\n## Captain'"'"'s intent\nRebind fixture %s.\n\n## Firstmate spec\nStay idle.\n' "$id" > "$LAB/data/$id/brief.md"
done

PATH="$FAKEBIN:$PATH" "$ROOT/bin/fm-herdr-lab.sh" provision "$SESSION" || { say "provision failed"; exit 1; }
LAB_READY=1
say "lab session: $SESSION (herdr $(herdr --version))"

# The launcher seat: a 'firstmate' workspace whose root pane runs every command,
# mirroring a firstmate primary sitting in its own Herdr workspace.
OUT=$(lab workspace create --cwd "$ROOT" --label firstmate --focus) || { say "launcher create failed"; exit 1; }
LWS=$(printf '%s' "$OUT" | jq -r '.result.workspace.workspace_id')
LPANE=$(printf '%s' "$OUT" | jq -r '.result.root_pane.pane_id')
say "launcher workspace=$LWS pane=$LPANE"
sleep 1

STEP=0
in_pane() {  # <description> <command...>: run in the launcher pane, wait, print output
  STEP=$((STEP + 1))
  local desc=$1; shift
  local script="$SCR/step$STEP.sh" i
  {
    printf '#!/usr/bin/env bash\ncd %q || exit 99\n' "$ROOT"
    printf 'env -u NO_MISTAKES_GATE -u FM_GATE_REFUSE_BYPASS -u FM_ROOT_OVERRIDE -u FM_STATE_OVERRIDE -u FM_DATA_OVERRIDE -u FM_CONFIG_OVERRIDE -u FM_PROJECTS_OVERRIDE FM_HOME=%q CLAUDE_CONFIG_DIR=%q FM_SPAWN_NO_GUARD=1 PATH=%q' "$LAB" "$SCR/claude-config" "$FAKEBIN:$PATH"
    printf ' %q' "$@"
    printf ' > %q 2>&1\necho $? > %q\n' "$SCR/step$STEP.out" "$SCR/step$STEP.rc"
  } > "$script"
  chmod +x "$script"
  lab pane send-text "$LPANE" "bash $script" >/dev/null
  lab pane send-keys "$LPANE" Enter >/dev/null
  for i in $(seq 1 450); do [ -f "$SCR/step$STEP.rc" ] && break; sleep 0.2; done
  say ""
  say "=== step $STEP: $desc"
  say "\$ (in launcher pane $LPANE, HERDR_PANE_ID set by herdr) $*"
  sed 's/^/    /' "$SCR/step$STEP.out" 2>/dev/null | tee -a "$LOG" >/dev/null
  say "    [exit $(cat "$SCR/step$STEP.rc" 2>/dev/null || echo TIMEOUT)]"
}
layout() {  # <title>
  local ws
  say ""
  say "--- herdr layout: $1"
  lab workspace list | jq -r '.result.workspaces[] | "\(.workspace_id)\t\(.label)"' | while IFS=$'\t' read -r ws label; do
    say "  workspace $ws \"$label\""
    lab tab list --workspace "$ws" | jq -r '.result.tabs[] | "      tab \(.tab_id) \"\(.label)\""' | tee -a "$LOG"
  done
}
meta() { grep -E "^(window|herdr_workspace_id|harness)=" "$LAB/state/$1.meta" | sed 's/^/    meta: /' | tee -a "$LOG"; }
journal() { if [ -f "$LAB/state/$1.herdr-presentation" ]; then sed 's/^/    journal: /' "$LAB/state/$1.herdr-presentation" | tee -a "$LOG"; else say "    journal: <absent>"; fi; }
remember_wt() { local wt; wt=$(sed -n 's/^worktree=//p' "$LAB/state/$1.meta" | tail -1); WTS="$WTS $wt"; }

# ---------- Scenario 1: fresh spawn, endpoint destroyed, relaunch --harness claude --note "switched from pi to claude after the endpoint was proven gone"
in_pane "fresh ship spawn rbp (presentation spaces default)" \
  bin/fm-spawn.sh rbp "$PROJ" pi --mode no-mistakes --yolo off --backend herdr
remember_wt rbp
layout "after fresh spawn of rbp"; meta rbp; journal rbp
OLD_WS=$(sed -n 's/^herdr_workspace_id=//p' "$LAB/state/rbp.meta" | tail -1)
say ""; say "=== destroy rbp's endpoint: close its presentation workspace $OLD_WS (the w6K-gone shape)"
lab workspace close "$OLD_WS" >/dev/null && say "    closed"
sleep 1
layout "after destroying rbp's endpoint"
in_pane "reclaim rbp onto claude" bin/fm-control.sh rbp relaunch --harness claude --note "switched from pi to claude after the endpoint was proven gone"
layout "after relaunch of rbp"; meta rbp; journal rbp
say "    pi launches: $(cat "$SCR/pi-launches" 2>/dev/null)"
say "    claude launches: $(cat "$SCR/claude-launches" 2>/dev/null)"

# ---------- Scenario 3 (adversarial): journal still names a present workspace
NEW_WS=$(sed -n 's/^herdr_workspace_id=//p' "$LAB/state/rbp.meta" | tail -1)
TOKEN=$(sed -n 's/^projection_id=//p' "$LAB/state/rbp.herdr-presentation" | tail -1)
say ""; say "=== adversarial: plant a decoy workspace still carrying rbp's journal token, then destroy the real endpoint"
lab workspace create --cwd "$SCR" --label "└ rbp · p:$TOKEN" --no-focus >/dev/null 2>&1 || lab workspace create --cwd "$SCR" --label "└ rbp · p:$TOKEN" >/dev/null
lab workspace focus "$LWS" >/dev/null 2>&1 || true
lab workspace close "$NEW_WS" >/dev/null && say "    closed real projected workspace $NEW_WS"
cp "$LAB/state/rbp.herdr-presentation" "$SCR/journal-before"
sleep 1
layout "before adversarial relaunch"
in_pane "reclaim rbp while a token-bearing space is still present" bin/fm-control.sh rbp relaunch --harness claude --note "switched from pi to claude after the endpoint was proven gone"
layout "after adversarial relaunch"; meta rbp; journal rbp
if cmp -s "$SCR/journal-before" "$LAB/state/rbp.herdr-presentation"; then say "    journal byte-identical to before: yes"; else say "    journal byte-identical to before: NO"; fi

# ---------- Scenario 2: presentation spaces off keeps the flat layout
printf 'off\n' > "$LAB/config/herdr-presentation-spaces"
in_pane "fresh ship spawn rbo with presentation spaces off" \
  bin/fm-spawn.sh rbo "$PROJ" pi --mode no-mistakes --yolo off --backend herdr
remember_wt rbo
RBO_PANE=$(sed -n 's/^window=//p' "$LAB/state/rbo.meta" | tail -1); RBO_PANE=${RBO_PANE#*:}
say ""; say "=== destroy rbo's endpoint: close pane $RBO_PANE"
lab pane close "$RBO_PANE" >/dev/null && say "    closed"
sleep 1
in_pane "reclaim rbo with presentation spaces off" bin/fm-control.sh rbo relaunch --harness claude --note "switched from pi to claude after the endpoint was proven gone"
layout "after relaunch of rbo (off)"; meta rbo; journal rbo
say ""; say "=== done"
