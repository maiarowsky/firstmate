import os
import hashlib
import pathlib
import shlex
import shutil
import subprocess
import time
import uuid

ROOT = pathlib.Path.cwd()
EVIDENCE = pathlib.Path('/Users/jaroslawmacioszek/.no-mistakes/evidence/01M45B82ANJF07B6F1VXXV80JH')
WORK = ROOT / '.validation-temp/live-hooks'
SOCKET = ROOT / ('.s' + uuid.uuid4().hex[:6])
BASH = shutil.which('bash')
TMUX = shutil.which('tmux')
NATIVE = shutil.which('git')
LEGACY = subprocess.check_output(['/usr/bin/env', 'PATH=/usr/bin:/bin:/usr/sbin:/sbin', 'which', 'git'], text=True).strip()
CLEAN = dict(os.environ)
for key in list(CLEAN):
    if key.startswith('GIT_CONFIG_') or key.startswith('FM_') or key in ('TMUX', 'TMUX_PANE', 'CLAUDE_CONFIG_DIR', 'TASKS_AXI_FILE', 'TASKS_AXI_BACKEND'):
        CLEAN.pop(key, None)
CLEAN.update(GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1', TMPDIR=str(ROOT / '.validation-temp'))
LOG = []
IDS = []
HOMES = []


def log(text):
    LOG.append(text)
    print(text, flush=True)


def run(args, env=None, check=True, cwd=None):
    proc = subprocess.run([str(x) for x in args], env=env or CLEAN, cwd=cwd or ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    if check and proc.returncode:
        raise RuntimeError(f'{shlex.join([str(x) for x in args])}: exit {proc.returncode}\n{proc.stdout}')
    return proc


def mux(*args, **kwargs):
    return run([TMUX, '-S', SOCKET, *args], **kwargs)


def git(repo, *args, env=None, check=True):
    return run([NATIVE, '-C', repo, *args], env=env, check=check)


def wait_path(path, timeout=15):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if path.exists():
            return
        time.sleep(.1)
    raise RuntimeError(f'timed out waiting for {path}')


def write(path, content, executable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    if executable:
        path.chmod(0o700)


try:
    WORK.mkdir(parents=True, exist_ok=True)
    log('Live product: fm-spawn --relaunch into seeded, agent-free disposable tmux workers; no models, fake Git, or fake terminal backend.')
    log(run([NATIVE, '--version']).stdout.strip())
    log(run([LEGACY, '--version']).stdout.strip())
    log(run([TMUX, '-V']).stdout.strip())
    mux('-f', '/dev/null', 'new-session', '-d', '-s', 'fm-lab-hooks', '-n', 'control', '-x', '120', '-y', '40', '-c', ROOT,
        f'{shlex.quote(BASH)} --noprofile --norc')
    socket_identity = mux('display-message', '-p', '-t', 'fm-lab-hooks:control', '#{socket_path},#{pid},0').stdout.strip()
    cases = [('legacy-to-native', False, LEGACY, NATIVE, False), ('legacy-to-native', True, LEGACY, NATIVE, False),
             ('native-to-legacy', False, NATIVE, LEGACY, False), ('native-to-legacy', True, NATIVE, LEGACY, False),
             ('keep-ai-trailers', True, NATIVE, NATIVE, True), ('hook-setup-refuses', False, NATIVE, NATIVE, False)]
    for label, allowlist, spawner_git, worker_git, keep in cases:
        tag = label + ('-allowlist' if allowlist else '-plain')
        case = WORK / tag
        home, proj, wt, tools = [case / x for x in ('home', 'project', 'wt', 'worker-bin')]
        case.mkdir()
        run([ROOT / 'bin/fm-lab-home.sh', 'create', home])
        HOMES.append(home)
        tools.mkdir()
        for name, executable in [('git', worker_git), ('bash', BASH), ('jq', shutil.which('jq'))]:
            (tools / name).symlink_to(executable)
        path = f'{tools}:/usr/bin:/bin:/usr/sbin:/sbin'
        write(home / 'config/backlog-backend', 'manual\n')
        if allowlist:
            write(home / 'config/launch-env-allowlist', '')
        if keep:
            write(home / 'config/keep-ai-trailers', '')
        git(proj, 'init', '-q', '-b', 'main', check=False) if proj.exists() else None
        proj.mkdir()
        git(proj, 'init', '-q', '-b', 'main')
        write(proj / 'README', 'Disposable hook validation project\n')
        write(proj / 'health-check', '''#!/bin/sh
set -eu
actual=$(git rev-parse --path-format=absolute --git-path hooks/pre-commit)
canonical="$PWD/project-hooks/pre-commit"
printf 'effective pre-commit: %s\ncanonical pre-commit: %s\n' "$actual" "$canonical"
[ -x "$actual" ] && [ "$actual" = "$canonical" ] || { echo 'effective Git pre-commit is non-executable or not the canonical guard'; exit 42; }
exit "${CHECK_EXIT:-0}"
''', True)
        write(proj / 'project-hooks/pre-commit', '''#!/bin/sh
printf 'pre-commit\n' >> hook-order
exit "${PRE_COMMIT_EXIT:-0}"
''', True)
        write(proj / 'project-hooks/prepare-commit-msg', '''#!/bin/sh
printf 'prepare-commit-msg\n' >> hook-order
printf '\nCo-authored-by: Claude <noreply@anthropic.com>\n' >> "$1"
''', True)
        write(proj / 'project-hooks/commit-msg', '''#!/bin/sh
printf 'commit-msg\n' >> hook-order
cp "$1" project-message
exit "${PROJECT_HOOK_EXIT:-0}"
''', True)
        write(proj / 'project-hooks/post-commit', '#!/bin/sh\nprintf "post-commit\\n" >> hook-order\n', True)
        write(proj / 'project-hooks/pre-push', '#!/bin/sh\nprintf "project pre-push refusal\\n"\nexit 19\n', True)
        git(proj, 'add', '.')
        git(proj, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'initial')
        id = 'hook-live-' + uuid.uuid4().hex[:10]
        IDS.append(id)
        git(proj, 'worktree', 'add', '-q', '-b', 'fm/' + id, wt)
        git(wt, 'config', 'user.name', 'Hook Fixture')
        git(wt, 'config', 'user.email', 'hook-fixture@example.invalid')
        git(wt, 'config', 'core.hooksPath', 'project-hooks')
        if worker_git == NATIVE:
            git(wt, 'config', 'hook.project.event', 'commit-msg')
            git(wt, 'config', 'hook.project.command', 'printf "config-commit-msg\\n" >> hook-order')
            git(wt, 'config', 'hook.firstmate-strip-ai-trailers.enabled', 'false')
        remote = case / 'remote.git'
        git(remote, 'init', '-q', '--bare', check=False) if remote.exists() else None
        remote.mkdir()
        git(remote, 'init', '-q', '--bare')
        git(wt, 'remote', 'add', 'origin', str(remote))
        write(home / f'data/{id}/brief.md', f'''# Task
## Captain's intent
Exercise ordinary project validation and commits with project hooks preserved.

## Firstmate spec
Run only the isolated hook validation command; do not use a model.

Delivery contract: mode=local-only
Ship branch: fm/{id}
''')
        write(home / f'state/{id}.meta', f'''window=fm-lab-hooks:fm-{id}
endpoint_task_id={id}
worktree={wt}
project={proj}
harness=sh
kind=ship
mode=local-only
yolo=off
branch=fm/{id}
model=default
effort=default
''')
        script = case / 'worker.sh'
        native = worker_git == NATIVE
        extra_health = './health-check; sh -c ./health-check; git -c "alias.health=!./health-check" health' if native else 'set +e; ./health-check; rc=$?; set -e; [ "$rc" = 42 ]; echo "authorized legacy identity-check limitation: exit $rc"'
        expected_order = 'pre-commit\nprepare-commit-msg\nconfig-commit-msg\ncommit-msg\npost-commit' if native else 'pre-commit\nprepare-commit-msg\ncommit-msg\npost-commit'
        worker = f'''#!/bin/sh
set -eu
exec > {shlex.quote(str(case / 'worker.log'))} 2>&1
printf 'worker git: '; git --version
printf 'worker grid: '; stty size
printf 'worker config keys:\\n'; git config --get-regexp '^(core.hookspath|hook\\.)' || true
{extra_health}
if [ {int(native)} = 1 ]; then
  head=$(git rev-parse HEAD)
  set +e; CHECK_EXIT=23 ./health-check && git commit --allow-empty -m unexpected; rc=$?; set -e
  [ "$rc" = 23 ]; [ "$head" = "$(git rev-parse HEAD)" ]; echo 'ordinary validation propagates exit 23 without committing'
fi
./health-check >/dev/null 2>&1 || [ {int(native)} = 0 ]
git commit --allow-empty --trailer 'Co-authored-by: Cursor <cursoragent@cursor.com>' --trailer 'Co-authored-by: Jane Doe <jane@example.com>' -m 'fix: live ordinary validation'
printf 'persisted commit:\\n'; git log -1 --format='%an <%ae>%n%B'
printf 'project commit-msg input:\\n'; cat project-message; cp project-message committed-project-message
printf 'hook order:\\n'; cat hook-order
printf 'expected hook order:\\n%s\\n' {shlex.quote(expected_order)}
head=$(git rev-parse HEAD)
set +e; PROJECT_HOOK_EXIT=7 git commit --allow-empty -m 'should refuse'; rc=$?; set -e
[ "$rc" != 0 ]; [ "$head" = "$(git rev-parse HEAD)" ]; echo "project commit-msg refusal: exit $rc, HEAD unchanged"
set +e; PRE_COMMIT_EXIT=17 git commit --allow-empty -m 'should also refuse'; rc=$?; set -e
[ "$rc" != 0 ]; [ "$head" = "$(git rev-parse HEAD)" ]; echo "project pre-commit refusal: exit $rc, HEAD unchanged"
set +e; git -c 'alias.guarded-push=!git push origin HEAD:refs/heads/rejected' guarded-push; rc=$?; set -e
[ "$rc" != 0 ]; ! git --git-dir={shlex.quote(str(remote))} show-ref --verify --quiet refs/heads/rejected; echo "child Git project pre-push refusal: exit $rc, remote unchanged"
touch {shlex.quote(str(case / 'done'))}
'''
        if label == 'hook-setup-refuses':
            worker = f'touch {shlex.quote(str(case / "first-step"))}; touch {shlex.quote(str(case / "second-step"))}'
            write(case / 'broken-config', '[malformed\n')
        write(script, worker, True)
        args = ['new-window', '-d', '-n', f'fm-{id}', '-t', 'fm-lab-hooks:', '-c', wt,
                '-e', f'HOME={home}', '-e', f'PATH={path}', '-e', 'GIT_CONFIG_GLOBAL=/dev/null', '-e', 'GIT_CONFIG_NOSYSTEM=1',
                '-e', f'TMPDIR={ROOT / ".validation-temp"}']
        if label == 'hook-setup-refuses':
            args += ['-e', f'GIT_CONFIG_GLOBAL={case / "broken-config"}']
        # tmux's outer command shell can rewrite PATH during startup; pin it for the actual worker shell after that startup.
        args += [f'/usr/bin/env PATH={shlex.quote(path)} HOME={shlex.quote(str(home))} {shlex.quote(BASH)} --noprofile --norc']
        mux(*args)
        if label == 'hook-setup-refuses':
            mux('pipe-pane', '-t', f'fm-lab-hooks:fm-{id}', f'/bin/cat > {shlex.quote(str(case / "pane-stream.log"))}')
        time.sleep(.25)
        spawnenv = dict(CLEAN, FM_HOME=str(home), HOME=str(home), TMUX=socket_identity,
                        PATH=f'{pathlib.Path(spawner_git).parent}:/usr/bin:/bin:/opt/homebrew/bin', FM_SPAWN_NO_GUARD='1')
        log(f'\n=== {tag}: spawner {run([spawner_git, "--version"]).stdout.strip()} / destination {run([worker_git, "--version"]).stdout.strip()} ===')
        raw = f'/bin/sh {shlex.quote(str(script))}'
        if label == 'hook-setup-refuses':
            raw = worker
        result = run([ROOT / 'bin/fm-spawn.sh', id, '--relaunch', '--harness', raw], env=spawnenv)
        log(result.stdout.strip())
        if label == 'hook-setup-refuses':
            time.sleep(1)
            assert not (case / 'first-step').exists() and not (case / 'second-step').exists()
            # exit from the destination hook setup closes the pane before either raw step.
            assert mux('list-windows', '-t', 'fm-lab-hooks', '-F', '#{window_name}').stdout.splitlines() == ['control'] or f'fm-{id}' not in mux('list-windows', '-t', 'fm-lab-hooks', '-F', '#{window_name}').stdout.splitlines()
            errors = (case / 'pane-stream.log').read_text()
            assert 'bad config line' in errors
            log('Actual destination shell diagnostic:\n' + errors)
            log('Malformed destination Git configuration refused hook setup; neither compound launch step ran and the worker shell exited.')
            continue
        try:
            wait_path(case / 'done')
        except RuntimeError:
            if (case / 'worker.log').exists():
                log((case / 'worker.log').read_text())
            log(mux('capture-pane', '-p', '-t', f'fm-lab-hooks:fm-{id}', '-S', '-100', check=False).stdout)
            raise
        text = (case / 'worker.log').read_text()
        log(text)
        capture = mux('capture-pane', '-p', '-t', f'fm-lab-hooks:fm-{id}', '-S', '-80').stdout
        write(EVIDENCE / f'{tag}-pane.txt', capture)
        log('actual pane setup/launch transcript:\n' + capture)
        body = git(wt, 'log', '-1', '--format=%B').stdout
        assert ('cursoragent@cursor.com' in body) == keep
        assert ('noreply@anthropic.com' in body) == keep
        assert 'Jane Doe <jane@example.com>' in body
        assert git(wt, 'log', '-1', '--format=%an <%ae>').stdout.strip() == 'Hook Fixture <hook-fixture@example.invalid>'
        assert (wt / 'committed-project-message').read_text().strip() == body.strip()
        order = (wt / 'hook-order').read_text().splitlines()
        assert order[:5 if native else 4] == expected_order.splitlines()
        if not native:
            assert 'canonical project-hook checks may fail' in capture.replace('\n', '')
            assert (home / f'state/{id}.git-hooks').is_dir()
        else:
            assert not (home / f'state/{id}.git-hooks').exists()
            assert 'using legacy' not in capture
        log(f'{tag}: ordinary commit, identity, project hooks, hook ordering, guard refusals, and attribution policy verified against persisted Git state.')
        mux('kill-window', '-t', f'fm-lab-hooks:fm-{id}')
    log('\nAll live scenarios completed. Only the private fm-lab-hooks tmux server was used.')
except BaseException as error:
    log(f'LIVE VALIDATION ERROR: {error}')
    raise
finally:
    mux('kill-server', check=False)
    SOCKET.unlink(missing_ok=True)
    write(EVIDENCE / 'live-spawn-hooks-transcript.txt', '\n'.join(LOG) + '\n')
    # Disposable product temp files are generated by fm-spawn itself; remove only namespaces for this run.
    for id, home in zip(IDS, HOMES):
        token = hashlib.sha256(str(home).encode()).hexdigest()
        for path in (pathlib.Path(f'/tmp/fm-{id}'), pathlib.Path(f'/tmp/fm-{id}+{token}')):
            shutil.rmtree(path, ignore_errors=True)
    if WORK.exists():
        for directory, subdirs, files in os.walk(WORK):
            os.chmod(directory, 0o700)
        shutil.rmtree(WORK)
