import ast
import difflib
import pathlib
import sys

xship_dir = pathlib.Path(sys.argv[1])
xvault_dir = pathlib.Path(sys.argv[2])
out_dir = pathlib.Path(sys.argv[3])
out_dir.mkdir(parents=True, exist_ok=True)
diff_dir = out_dir / 'diffs'
diff_dir.mkdir(parents=True, exist_ok=True)


def methods(text):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result.add(node.name)
    return result

xship_files = {p.name: p for p in xship_dir.glob('*.py') if p.name != '__init__.py'}
xvault_files = {p.name: p for p in xvault_dir.glob('*.py') if p.name != '__init__.py'}
all_names = sorted(set(xship_files) | set(xvault_files))
rows = []

for name in all_names:
    xp = xship_files.get(name)
    vp = xvault_files.get(name)
    if not xp:
        rows.append((name, 'nur xVault', '', '', '', ''))
        continue
    if not vp:
        rows.append((name, 'nur xShip', '', '', '', ''))
        continue

    xs = xp.read_text(encoding='utf-8', errors='replace')
    vs = vp.read_text(encoding='utf-8', errors='replace')
    if xs == vs:
        rows.append((name, 'identisch', '100%', '', '', ''))
        continue

    ratio = difflib.SequenceMatcher(None, xs, vs).ratio() * 100
    xm = methods(xs)
    vm = methods(vs)
    vonly = ', '.join(sorted(vm - xm))
    xonly = ', '.join(sorted(xm - vm))
    diff = ''.join(difflib.unified_diff(
        xs.splitlines(True), vs.splitlines(True),
        fromfile='xShip/' + name, tofile='xVault/' + name, n=3,
    ))
    (diff_dir / (name + '.diff')).write_text(diff, encoding='utf-8')
    rows.append((name, 'abweichend', f'{ratio:.1f}%', str(len(xs)), str(len(vs)), vonly + (' | xShip-only: ' + xonly if xonly else '')))

lines = [
    '# xShip 2026.08.31.2 vs xVault main – Scrapervergleich',
    '',
    '| Scraper | Status | Ähnlichkeit | xShip Bytes | xVault Bytes | Zusätzliche Funktionen |',
    '|---|---|---:|---:|---:|---|',
]
for row in rows:
    safe = [str(v).replace('|', '\\|').replace('\n', ' ') for v in row]
    lines.append('| ' + ' | '.join(safe) + ' |')

lines += [
    '',
    '## Zusammenfassung',
    '',
    f'- xShip Scraper: {len(xship_files)}',
    f'- xVault Site-Scraper: {len(xvault_files)}',
    f'- Identisch: {sum(1 for r in rows if r[1] == "identisch")}',
    f'- Abweichend: {sum(1 for r in rows if r[1] == "abweichend")}',
    f'- Nur xShip: {sum(1 for r in rows if r[1] == "nur xShip")}',
    f'- Nur xVault: {sum(1 for r in rows if r[1] == "nur xVault")}',
    '',
    'Für jeden abweichenden gemeinsamen Scraper liegt unter `diffs/` ein Unified Diff.',
]
(out_dir / 'scraper-comparison.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('\n'.join(lines))
