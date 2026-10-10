import html
import json
import pathlib
import re

root = pathlib.Path('/Users/jaroslawmacioszek/.no-mistakes/evidence/01M4K30EK3AB66P87XY0KKNBAV')
sgr = re.compile(r'\x1b\[([0-9;]*)m')
ansi = ['#000000', '#cd0000', '#00cd00', '#cdcd00', '#0000ee', '#cd00cd', '#00cdcd', '#e5e5e5', '#7f7f7f', '#ff0000', '#00ff00', '#ffff00', '#5c5cff', '#ff00ff', '#00ffff', '#ffffff']

def color(n):
    if n < 16:
        return ansi[n]
    if n < 232:
        n -= 16
        levels = [0, 95, 135, 175, 215, 255]
        return '#%02x%02x%02x' % (levels[n // 36], levels[n // 6 % 6], levels[n % 6])
    return '#%02x%02x%02x' % ((8 + 10 * (n - 232),) * 3)

def render(screen):
    state = {}
    out = []
    at = 0
    def text(value):
        css = []
        fg = state.get('fg', '#dddddd')
        bg = state.get('bg', '#111111')
        if state.get('reverse'):
            fg, bg = bg, fg
        css += ['color:' + fg, 'background:' + bg]
        if state.get('dim'):
            css.append('opacity:.6')
        if state.get('bold'):
            css.append('font-weight:700')
        out.append('<span style="' + ';'.join(css) + '">' + html.escape(value) + '</span>')
    for match in sgr.finditer(screen):
        text(screen[at:match.start()])
        codes = [int(v or 0) for v in match[1].split(';')]
        i = 0
        while i < len(codes):
            c = codes[i]
            if c == 0:
                state.clear()
            elif c in [1, 2, 7]:
                state[{1: 'bold', 2: 'dim', 7: 'reverse'}[c]] = True
            elif c == 22:
                state.pop('dim', None); state.pop('bold', None)
            elif c == 27:
                state.pop('reverse', None)
            elif c in [39, 49]:
                state.pop({39:'fg',49:'bg'}[c], None)
            elif 30 <= c <= 37 or 90 <= c <= 97:
                state['fg'] = color(c - 30 if c < 90 else c - 90 + 8)
            elif 40 <= c <= 47 or 100 <= c <= 107:
                state['bg'] = color(c - 40 if c < 100 else c - 100 + 8)
            elif c in [38, 48] and i + 1 < len(codes):
                key = 'fg' if c == 38 else 'bg'
                if codes[i + 1] == 5 and i + 2 < len(codes):
                    state[key] = color(codes[i + 2]); i += 2
                elif codes[i + 1] == 2 and i + 4 < len(codes):
                    state[key] = '#%02x%02x%02x' % tuple(codes[i + 2:i + 5]); i += 4
            i += 1
        at = match.end()
    text(screen[at:])
    return ''.join(out)

frames = [
    ('Idle dollar-first subscription footer', 'control-idle.ansi'),
    ('Unsubmitted draft preserved after fm-control exit refusal', 'control-draft-1-preserved.ansi'),
    ('Glyph-only draft preserved', 'control-draft-2-preserved.ansi'),
    ('Cost-like text inside the composer preserved', 'control-draft-3-preserved.ansi'),
    ('Placeholder-like text is actual pending input', 'control-draft-4-preserved.ansi'),
    ('Ctrl+U and idle interrupt leave a genuinely empty composer', 'control-idle-after-interrupt.ansi'),
    ('Verified /quit stops Pi and leaves the worker shell endpoint', 'control-stopped-shell.ansi'),
]
parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>Live Pi composer evidence</title><style>body{margin:30px;background:#f3f4f6;color:#16202b;font:16px system-ui}h1{font-size:25px}h2{font-size:19px;margin-top:30px}pre{background:#111;color:#ddd;padding:18px;overflow:auto;line-height:1.25;font:12px Menlo,Consolas,monospace;border-radius:6px}p{max-width:90ch}code{font-family:monospace}</style><h1>Live Pi composer and control-plane evidence</h1><p>Actual ANSI terminal viewport exports from Pi 0.99.1, driven in a disposable private tmux server at 160 × 40. Profile: <code>openai-codex/gpt-6.1-sol xhigh</code>; offline, no model prompt submitted, no usable credentials. These are rendered terminal captures, not desktop screenshots. Source captures and control-live.log are adjacent artifacts.</p>']
for title, file in frames:
    parts.append('<section><h2>' + html.escape(title) + '</h2><p>Source: <code>' + file + '</code></p><pre>' + render((root / file).read_text()) + '</pre></section>')
parts.append('<h2>Observed lifecycle output</h2><pre>' + html.escape((root / 'control-live.log').read_text()) + '</pre></html>')
(root / 'pi-terminal-evidence.html').write_text('\n'.join(parts))
print('Rendered live ANSI viewport evidence: ' + str(root / 'pi-terminal-evidence.html'))
