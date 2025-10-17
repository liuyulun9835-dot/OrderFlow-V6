import pathlib
import re
import csv

ROOT = pathlib.Path('.')
patterns = {
    r"from\s+orderflow_v6\.preprocessing\s+import\s+(\w+)": r"from data import \1",
    r"from\s+orderflow_v6\.models\s+import\s+(\w+)": r"from model import \1",
    r"from\s+orderflow_v6\.strategy_core\s+import\s+(\w+)": r"from decision import \1",
}

changed: list[str] = []
for py in ROOT.rglob('*.py'):
    if 'compat' in py.parts:
        continue
    s = py.read_text(encoding='utf-8', errors='ignore')
    s_new = s
    for pat, rep in patterns.items():
        s_new = re.sub(pat, rep, s_new)
    if s_new != s:
        py.write_text(s_new, encoding='utf-8')
        changed.append(str(py))

path = ROOT / 'docs/migrations/import_rewrites.csv'
path.parent.mkdir(parents=True, exist_ok=True)
with path.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['file'])
    for c in changed:
        w.writerow([c])

print(f'Rewrote {len(changed)} files.')
