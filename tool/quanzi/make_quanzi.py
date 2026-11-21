"""全字版单字表：正式单字表原样保留，再把 chai 里所有带读音、正式表没收的字按机器拆分补进去（作者 2026-11-21）。
- 拆分：tool/quanzi/chai_split.ts 用 chai 算法按现行字根拆（out/splits_chai.json）；竹字头 chai 拆成 𠂉丶𠂉丶，这里并回 ⺮。
- 读音：chai 的 dictionary.txt（~/.cache/chai-data，assets.chaifen.app/dictionary.txt），每个读音出一个码。
- 码：双拼 + 首根键 + 末根键（只有一个根的字重复这个键），同码排在正式表原有的字后面，新字之间按 chai 字频。
- 简码：二码、三码位在整张表里都空着的，给新字补上（字频高的先得）；其余不管，也不做测试。
用法：.venv/bin/python tool/quanzi/make_quanzi.py <正式单字表> <布局 json> <双拼 xiaohe|ziranma> <输出>
"""
import collections, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'lib'))
from shuangpin import encode

base_path, layout_path, scheme, out_path = sys.argv[1:5]
groups = json.load(open(ROOT / 'build/out/n30/meta.json', encoding='utf-8'))['groups']
layout = json.load(open(layout_path, encoding='utf-8'))
key = {r: layout[g] for g, rs in groups.items() for r in rs}

base = [tuple(l.rstrip('\n').split('\t')[:2]) for l in open(base_path, encoding='utf-8-sig') if '\t' in l]
have = {t for t, _ in base}
slots = collections.defaultdict(list)
for t, c in base: slots[c].append(t)

splits = json.load(open(ROOT / 'tool/quanzi/out/splits_chai.json', encoding='utf-8'))
reads, freq = collections.defaultdict(list), collections.Counter()
for l in open(Path.home() / '.cache/chai-data/dictionary.txt', encoding='utf-8'):
    p = l.rstrip('\n').split('\t')
    if len(p) >= 2 and len(p[0]) == 1 and p[1]:
        if p[1] not in reads[p[0]]: reads[p[0]].append(p[1])
        freq[p[0]] += int(p[2]) if len(p) > 2 and p[2].isdigit() else 0


def fix(seq):                                           # chai 的竹字头 = 𠂉 丶 𠂉 丶
    out, i = [], 0
    while i < len(seq):
        if seq[i:i + 4] == ['𠂉', '丶', '𠂉', '丶']: out.append('⺮'); i += 4
        else: out.append(seq[i]); i += 1
    return out


new, skipped = [], collections.Counter()
for ch in sorted(set(reads) - have, key=lambda c: (-freq[c], c)):
    seq = fix(splits.get(ch, []))
    if not seq: skipped['无拆分'] += 1; continue
    if seq[0] not in key or seq[-1] not in key: skipped['根不在根表'] += 1; continue
    shape = key[seq[0]] + key[seq[-1]]
    for py in reads[ch]:
        try: sp = encode(py, scheme)
        except Exception: skipped['读音换不了双拼'] += 1; continue
        new.append((ch, sp + shape))
new = list(dict.fromkeys(new))
for ch, code in new: slots[code].append(ch)

filled = 0                                              # 空着的二码、三码位给新字（按字频）
for ch, code in new:
    for short in (code[:2], code[:3]):
        if not slots.get(short):
            slots[short] = [ch]; filled += 1; break

lines = [f'{t}\t{c}\n' for c in sorted(slots) for t in dict.fromkeys(slots[c])]
Path(out_path).write_text(''.join(lines), encoding='utf-8')
print(f'正式表 {len(have)} 字；新增 {len({c for c, _ in new})} 字 {len(new)} 码；补简码 {filled}；跳过 {dict(skipped)}；共 {len({l.split(chr(9))[0] for l in lines})} 字 {len(lines)} 行 → {out_path}')
