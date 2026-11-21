"""夜莺版万象：在万象拼音 PRO（带辅助码版）上只换辅助码，其余（方案、Lua、词库词条与词频、语法模型）一律不动（作者 2026-11-21）。
手机上要整句时用（万象靠 Rime 自带的 octagram 语法模型，同文、仓输入法都能用；夜莺 V5 的魔虎运行库只有电脑版）。
- 辅助码：每个字每个读音换成夜莺全码的后两位（首根＋末根），按读音取；正式表没有的字用全字版（tool/quanzi）的机器拆分码。
  一个读音有两个夜莺辅码（如保留的旧拆法）时写成两组（万象格式 拼音;码1,码2）。
- 拆分提示 lua/data/chaifen.txt：换成夜莺拆分＋辅码（正式拆分取 Bime 拆分表，其余取 chai 机器拆分）。
- 双拼默认小鹤；方案菜单名“夜莺万象”，方案 ID 仍是 wanxiang_pro（万象的 Lua 按这个 ID 工作）。
- 语法模型 wanxiang-lts-zh-hans.gram（391MB）不打进包里，按万象的做法另下，放进用户目录（没有也能打字，只是整句差一些）。
用法：.venv/bin/python tool/wanxiang/make_wanxiang.py <万象 pro 辅助码版 zip> <全字版单字表> <Bime 拆分表> <输出目录>
"""
import collections, json, re, shutil, sys, unicodedata, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'lib'))
from shuangpin import encode

src, table, split_path, out = map(Path, sys.argv[1:5])
SCHEME, NAME = 'xiaohe', '夜莺万象'
if out.exists(): shutil.rmtree(out)
zipfile.ZipFile(src).extractall(out)
stat = collections.Counter()

# ---- 夜莺辅码：(字, 双拼) → [辅码…]；字 → [辅码…]（读音对不上时用） ----
by_sound, by_char = collections.defaultdict(list), collections.defaultdict(list)
for l in open(table, encoding='utf-8-sig'):
    t, c = l.rstrip('\n').split('\t')[:2]
    if len(t) != 1 or len(c) != 4 or 'CJK' not in unicodedata.name(t, ''): continue
    if c[2:] not in by_sound[t, c[:2]]: by_sound[t, c[:2]].append(c[2:])
    if c[2:] not in by_char[t]: by_char[t].append(c[2:])


def plain(py):                                          # 带调拼音 → 无调（ü 作 v）
    s = unicodedata.normalize('NFD', py.replace('ü', 'v').replace('Ü', 'v'))
    return ''.join(ch for ch in s if not unicodedata.combining(ch)).replace('v̈', 'v').lower()


def aux(ch, py):
    try: sp = encode(plain(py), SCHEME)
    except Exception: sp = None
    a = by_sound.get((ch, sp)) or by_char.get(ch)
    return ','.join(a[:2]) if a else ''


# ---- 词库：逐音节换辅码 ----
HAN = lambda c: 'CJK' in unicodedata.name(c, '') or '〇' == c
for p in sorted((out / 'dicts').glob('*.pro.dict.yaml')):
    lines, body = [], False
    for l in p.read_text(encoding='utf-8').split('\n'):
        if l.startswith('...'): body = True; lines.append(l); continue
        f = l.split('\t')
        if not body or l.startswith('#') or len(f) < 2 or ';' not in f[1]:
            lines.append(l); continue
        chars = [c for c in f[0] if HAN(c)]
        toks = f[1].split(' ')
        if len(chars) != len(toks):
            stat['字数与音节数不符（原样）'] += 1; lines.append(l); continue
        new = []
        for ch, tok in zip(chars, toks):
            py = tok.split(';')[0]
            a = aux(ch, py)
            if not a: stat['没有夜莺码的字（去掉辅码）'] += 1
            new.append(f'{py};{a}')
        f[1] = ' '.join(new)
        if f[1] != l.split('\t')[1]: stat['改码行'] += 1
        lines.append('\t'.join(f))
    p.write_text('\n'.join(lines), encoding='utf-8')

# ---- 拆分提示：夜莺拆分＋辅码 ----
split = {}
for l in open(split_path, encoding='utf-8-sig'):
    t, s = l.rstrip('\n').split('\t', 1); split[t] = s.replace(' ＋ ', '')
chai = json.load(open(ROOT / 'tool/quanzi/out/splits_chai.json', encoding='utf-8'))


def fix(seq):                                           # chai 的竹字头 = 𠂉 丶 𠂉 丶
    o, i = [], 0
    while i < len(seq):
        if seq[i:i + 4] == ['𠂉', '丶', '𠂉', '丶']: o.append('⺮'); i += 4
        else: o.append(seq[i]); i += 1
    return o


tips = []
for t, a in by_char.items():
    s = split.get(t) or ''.join(fix(chai.get(t, [])))
    if s: tips.append(f'{t}\t{s} {a[0]}')
(out / 'lua/data/chaifen.txt').write_text('\n'.join(tips) + '\n', encoding='utf-8')
stat['拆分提示'] = len(tips)

# ---- 方案：小鹤双拼、菜单名 ----
sch = out / 'wanxiang_pro.schema.yaml'; s = sch.read_text(encoding='utf-8')
assert s.count('      - wanxiang_algebra:/pro/自然码  #拼音转双拼码') == 1 and s.count('  name: 万象拼音PRO\n') == 1
s = s.replace('      - wanxiang_algebra:/pro/自然码  #拼音转双拼码', '      - wanxiang_algebra:/pro/小鹤双拼  #拼音转双拼码（夜莺：小鹤）')
s = s.replace('  name: 万象拼音PRO\n', f'  name: {NAME}\n')
sch.write_text(s, encoding='utf-8')
(out / 'default.custom.yaml').write_text('patch:\n  schema_list:\n    - schema: wanxiang_pro\n', encoding='utf-8')
print(out, dict(stat), '夜莺辅码字', len(by_char))
