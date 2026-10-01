#!/usr/bin/env python3
"""Run real fm-pr-merge with real gh on already-merged incident PRs only.
No forge shims, status publications, pushes, or new GitHub resources.
All operational-home writes remain inside the gate worktree.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path('/Users/jaroslawmacioszek/.no-mistakes/worktrees/bd45d26a4aa0/01M3TS66QGJVKHGKSDGS4H3FD3')
EVIDENCE = Path('/Users/jaroslawmacioszek/.no-mistakes/evidence/01M3TS66QGJVKHGKSDGS4H3FD3')
HOME = ROOT / '.nm-test-step/live-home'
LOG = EVIDENCE / 'live-merge-refusals.log'
REPORT = EVIDENCE / 'live-merge-refusals.json'
ENV = {k: v for k, v in os.environ.items() if not k.startswith(('FM_', 'TASKS_AXI_'))}
ENV.update({
    'FM_ROOT_OVERRIDE': str(ROOT),
    'FM_HOME': str(HOME),
    'FM_STATE_OVERRIDE': str(HOME / 'state'),
    'FM_DATA_OVERRIDE': str(HOME / 'data'),
    'FM_CONFIG_OVERRIDE': str(HOME / 'config'),
    'FM_PROJECTS_OVERRIDE': str(HOME / 'projects'),
    'TMPDIR': str(ROOT / '.nm-test-step/tmp'),
    'GH_PROMPT_DISABLED': '1',
})
RESULTS = []


def run(command, env=ENV):
    cp = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=45)
    with LOG.open('a') as out:
        out.write('\n$ ' + ' '.join(command) + '\n')
        out.write(cp.stdout + cp.stderr)
        out.write(f'\nEXIT: {cp.returncode}\n')
    return cp


def check(name, cp, expected, forbidden=()):
    output = cp.stdout + cp.stderr
    ok = cp.returncode == 1 and all(text in output for text in expected) and not any(text in output for text in forbidden)
    RESULTS.append({'name': name, 'pass': ok, 'exit': cp.returncode})
    if not ok:
        raise AssertionError(f'{name}: exit {cp.returncode}; output {output}')


def prepare(number):
    url = f'https://github.com/maiarowsky/fortnight/pull/{number}'
    # The independent real forge read MUST prove a terminal PR before invoking
    # an entrypoint whose successful path would otherwise perform a merge.
    cp = run(['gh', 'pr', 'view', url, '--json', 'state,isDraft,mergeable,mergeStateStatus,headRefOid,baseRefName,statusCheckRollup'])
    if cp.returncode != 0:
        raise RuntimeError('live GitHub read unavailable: ' + cp.stderr)
    view = json.loads(cp.stdout)
    if view['state'] != 'MERGED':
        raise RuntimeError('refusing to validate on a non-terminal PR without merge authority')
    if HOME.exists():
        declaration = HOME / 'config/required-checks'
        if declaration.is_file() and not declaration.is_symlink():
            declaration.chmod(0o600)
        shutil.rmtree(HOME)
    for directory in ('state', 'data', 'config', 'projects'):
        (HOME / directory).mkdir(parents=True, mode=0o700)
    shutil.copyfile(ROOT / '.tasks.toml', HOME / '.tasks.toml')
    (HOME / 'data/backlog.md').write_text('## In flight\n\n## Queued\n\n## Done\n')
    meta = HOME / 'state/lab-merge-check.meta'
    meta.write_text(f'kind=ship\nmode=no-mistakes\nworktree={ROOT}\nproject={ROOT}\n')
    meta.chmod(0o600)
    return url, view


def product(url, *args, env=ENV):
    return run([str(ROOT / 'bin/fm-pr-merge.sh'), 'lab-merge-check', url, *args], env)


LOG.write_text('LIVE PRODUCT CHECK: real fm-pr-merge.sh and real authenticated gh.\n'
               'Safety scope: only already-merged incident PRs; no merge/status/push API mutations.\n'
               'Closed-state refusal remains an independent guard; these checks prove required-check diagnostics, not a new merge.\n')
try:
    for number in (745, 746, 748):
        url, view = prepare(number)
        declaration = HOME / 'config/required-checks'
        declaration.write_text('maiarowsky/fortnight validate\nmaiarowsky/fortnight autofirma/local-mac-gate\n')
        branch = run(['gh', 'api', f"repos/maiarowsky/fortnight/branches/{view['baseRefName']}", '--jq', '{name,protected,protection}'])
        rules = run(['gh', 'api', f"repos/maiarowsky/fortnight/rules/branches/{view['baseRefName']}"])
        assert branch.returncode == 0
        assert rules.returncode == 1 and 'HTTP 403' in rules.stderr and 'Upgrade to GitHub Pro' in rules.stderr
        cp = product(url)
        check(f'PR {number}: missing Mac status is diagnosed at the actual head despite plan 403', cp,
              [f"required check 'autofirma/local-mac-gate' has not reported at head {view['headRefOid']}", 'state is "MERGED", not open'],
              ['branch rules for base branch', "required check 'validate' has not reported"])
        # Persisted metadata is a public operational-home record, not an assertion on implementation source.
        with LOG.open('a') as out:
            out.write('\nPersisted task metadata:\n' + (HOME / 'state/lab-merge-check.meta').read_text())
        after = run(['gh', 'pr', 'view', url, '--json', 'state,headRefOid'])
        assert after.returncode == 0 and json.loads(after.stdout) == {'state': 'MERGED', 'headRefOid': view['headRefOid']}

    url, view = prepare(745)
    declaration = HOME / 'config/required-checks'
    declaration.write_text('maiarowsky/fortnight validate\nmaiarowsky/fortnight autofirma/local-mac-gate\n')
    cp = product(url, '--allow-missing', 'validate')
    check('A different named waiver does not waive the missing Mac status', cp,
          [f"required check 'autofirma/local-mac-gate' has not reported at head {view['headRefOid']}"])

    for variant, text in [('missing-name', '# requirements\nother/repo\n'), ('control-character', '# requirements\nother/repo ci\r\n')]:
        url, _ = prepare(745)
        declaration = HOME / 'config/required-checks'
        declaration.write_text(text)
        cp = product(url, '--allow-missing', 'autofirma/local-mac-gate', '--allow-red', 'validate')
        check(f'Malformed {variant} declaration for another repository refuses even with waivers', cp,
              ['malformed required-check declaration', str(declaration), 'line 2'])

    for variant in ('directory', 'dangling-symlink', 'unreadable-file'):
        url, _ = prepare(745)
        declaration = HOME / 'config/required-checks'
        if variant == 'directory':
            declaration.mkdir()
        elif variant == 'dangling-symlink':
            declaration.symlink_to(HOME / 'absent')
        else:
            declaration.write_text('maiarowsky/fortnight autofirma/local-mac-gate\n')
            declaration.chmod(0)
        try:
            cp = product(url, '--allow-missing', 'autofirma/local-mac-gate')
            check(f'{variant} declaration refuses rather than adding no requirements', cp,
                  [f'required-check declarations in {declaration} could not be read'])
        finally:
            if variant == 'unreadable-file':
                declaration.chmod(0o600)

    url, view = prepare(745)
    (HOME / 'config/required-checks').write_text('invalid home configuration\n')
    alternate = HOME / 'alternate-config'
    alternate.mkdir()
    (alternate / 'required-checks').write_text(' # required checks\n\nother/repo Ignore this repository\n\tMAIAROWSKY/FORTNIGHT\tvalidate  \nmaiarowsky/fortnight validate')
    cp = product(url, env=dict(ENV, FM_CONFIG_OVERRIDE=str(alternate)))
    check('Config override, case-insensitive repo scoping, comments and duplicate check-run declarations work', cp,
          ['state is "MERGED", not open'], ['required check', 'malformed', 'could not be read'])
finally:
    REPORT.write_text(json.dumps(RESULTS, indent=2) + '\n')
    if HOME.exists():
        declaration = HOME / 'config/required-checks'
        if declaration.is_file() and not declaration.is_symlink():
            declaration.chmod(0o600)
        shutil.rmtree(HOME)

print(json.dumps(RESULTS, indent=2))
