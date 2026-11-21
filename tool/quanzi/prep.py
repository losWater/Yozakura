"""全字版第一步：生成 chai 拆分的输入 out/input.json（根表：chai 部件名 → 夜莺根名；要拆的字）。
要拆的字 = 读音表里的字 ∪ 正式拆分的字（验证用），且在 chai 字形库里。
读音表：魔然 tools/data/chars.txt（字\t拼音\t繁频\t简频，约 8.4 万字；作者 2026-11-21 定用魔然的读音）。
用法：.venv/bin/python tool/quanzi/prep.py [读音表]
接着：<bun> run tool/quanzi/chai_split.ts → .venv/bin/python tool/quanzi/make_quanzi.py …
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
READINGS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / '.cache/auxcmp/moran/tools/data/chars.txt'
REPERTOIRE = Path.home() / '编码理论极限研究/experiments/003-chai-inverse/repertoire.raw.json'   # chai 字形库（api.chaifen.app/repertoire/all）

roots = [r for g in json.load(open(ROOT / 'build/out/n30/meta.json', encoding='utf-8'))['groups'].values() for r in g]
raw = json.load(open(REPERTOIRE))
chars = {chr(x['unicode']) for x in raw}
names = {x['name']: chr(x['unicode']) for x in raw if x.get('name')}
STROKE = {'横': '1', '竖': '2', '撇': '3', '点': '4', '折': '5'}
rmap = {'6': '折'}                                       # chai 分类器的第 6 类（各种折笔）也归折
for r in roots:
    if r in STROKE: rmap[STROKE[r]] = r
    elif len(r) == 1 and r in chars: rmap[r] = r
    elif r in names: rmap[names[r]] = r                 # chai 里有同名的私用区部件
want = {l.split('\t')[0] for l in open(READINGS, encoding='utf-8') if not l.startswith('#') and '\t' in l}
want = {c for c in want if len(c) == 1}
want |= set(json.load(open(ROOT / 'data/baseline/splits.json', encoding='utf-8')))
(ROOT / 'tool/quanzi/out').mkdir(exist_ok=True)
json.dump({'roots': rmap, 'targets': sorted(want & chars)}, open(ROOT / 'tool/quanzi/out/input.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'根 {len(rmap)}（现行 {len(roots)} 个，chai 里找不到的：{[r for r in roots if r not in rmap.values()]}）；要拆 {len(want & chars)} 字，字形库没有 {len(want - chars)}')
