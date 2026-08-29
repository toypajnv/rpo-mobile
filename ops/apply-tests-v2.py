from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def replace_all(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'Marker not found in {path}: {old!r}')
    target.write_text(text.replace(old, new), encoding='utf-8')

replace_all('server/tests/test_upgrade_20260821.py', '"1.1.6"', '"2.0.0"')
replace_all('server/tests/test_regressions.py', 'dashboard.js?v=20260821-1', 'dashboard.js?v=20260829-2')
replace_all('server/tests/test_regressions.py', 'app.css?v=20260821-1', 'app.css?v=20260829-2')
replace_all('server/tests/test_regressions.py', 'За выбранный период нет нарядов-допусков.', 'За выбранный период и текущий фильтр нет нарядов-допусков.')
print('tests v2 markers updated')
