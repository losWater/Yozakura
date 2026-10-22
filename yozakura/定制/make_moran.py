"""夜桜版魔然：在魔然官方简体全量包上只换“码”——辅助码改用夜桜全码的后两位（首根＋末根），其余（方案、Lua、按键、模型、词库词条与词频）一律不动。
- moran.chars.dict.yaml：夜桜收的字按读音取夜桜辅码（该读音没有夜桜全码时取字的主辅码），一个字有几个夜桜辅码就出几行，首行原权重、其余 ×3/4（同魔然 gen_chars.py）；
- moran.base/tencent/moe/computer/words 词库：逐音节换成该字的夜桜辅码（同魔然 update-compact-dict 的做法，按读音取）；
- lua/zrmdb.txt（辅筛、提示）、opencc 拆分提示：换成夜桜辅码与夜桜拆分；拆分提示改用文本词典（免装 opencc 工具）；
- 夜桜没收的字保留魔然原辅码与原拆分提示，照样能打；
- moran_fixed_simp（字词定长码表）：用户自己的表，按 yozakura/定制/make_custom.py 只换单字。
用法：.venv/bin/python yozakura/定制/make_moran.py <魔然简体全量包解压目录> <魔然 moran_chai.txt（同版本）> <用户 moran_fixed_simp.dict.yaml> <输出目录>
"""
import collections, json, re, shutil, subprocess, sys, unicodedata
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SRC, CHAI, FIXED, OUT = map(Path, sys.argv[1:5])
B = json.load(open(ROOT / 'yozakura/品牌.json', encoding='utf-8'))

# ---- 夜桜辅码：字 → [主辅码, 其余…]；(字, 双拼) → 该读音的辅码 ----
custom = {c for c, _, _ in json.load(open(ROOT / 'yozakura/手动调整.json', encoding='utf-8')).get('自定义码', [])}   # 保留原拆法的码排在后面
by_sound, order = collections.defaultdict(list), collections.defaultdict(list)
for l in open(ROOT / 'yozakura' / B['单字表'], encoding='utf-8-sig'):
    t, c = l.rstrip('\n').split('\t')[:2]
    if len(t) != 1 or len(c) != 4: continue
    a = c[2:]
    if a not in by_sound[t, c[:2]]: by_sound[t, c[:2]].append(a)
    order[t].append((c in custom, c[:2] == 'pp', a))           # 偏旁读音（pp）的码不当主辅码
AUX = {t: list(dict.fromkeys(a for _, _, a in sorted(v, key=lambda x: x[:2]))) for t, v in order.items()}
aux_of = lambda ch, sp: (by_sound.get((ch, sp)) or AUX[ch])[0]
# 夜桜拆分：取本版码表导出里的 Bime 拆分表（字\t根 ＋ 根 ＋ …）
SPLITS = Path.home() / f'Downloads/{B["名称"]}_发布附件/{B["名称"]}_字词表与输入法/Bime/mb/{B["名称"]}/{B["名称"].removesuffix(B["版本"])}.拆分'
assert SPLITS.exists(), f'缺 {SPLITS}（先跑 release/export_platforms.py）'

if OUT.exists(): shutil.rmtree(OUT)
shutil.copytree(SRC, OUT)
stat = collections.Counter()

# ---- 单字表 ----
p = OUT / 'moran.chars.dict.yaml'; lines, done = [], set()
rows = collections.defaultdict(list)                            # (字, 双拼) → [(行号, 权重)]
src = p.read_text(encoding='utf-8').split('\n')
for i, l in enumerate(src):
    m = re.fullmatch(r'(\S)\t([a-z]{2});([a-z]{2})\t(\d+)', l)
    if m and m[1] in AUX: rows[m[1], m[2]].append(int(m[4]))
for l in src:
    m = re.fullmatch(r'(\S)\t([a-z]{2});([a-z]{2})\t(\d+)', l)
    if not (m and m[1] in AUX): lines.append(l); continue
    k = (m[1], m[2])
    if k in done: continue
    done.add(k); w = max(rows[k])
    auxes = list(dict.fromkeys((by_sound.get(k) or []) + AUX[m[1]]))
    lines += [f'{m[1]}\t{m[2]};{a}\t{w if n == 0 else w // 4 * 3}' for n, a in enumerate(auxes)]
    stat['单字读音'] += 1
p.write_text('\n'.join(lines), encoding='utf-8')

# ---- 词库 ----
for name in ('moran.base', 'moran.tencent', 'moran.moe', 'moran.computer', 'moran.words'):
    p = OUT / f'{name}.dict.yaml'
    if not p.exists(): continue
    out = []
    for l in p.read_text(encoding='utf-8').split('\n'):
        m = re.fullmatch(r'([^\t#][^\t]*)\t([a-z]{2};[a-z]{2}(?: [a-z]{2};[a-z]{2})*)(\t.*)?', l)
        if m:
            chars = [c for c in m[1] if unicodedata.category(c)[0] in 'LN']   # 只按字对应音节，标点（·，（）：–- 等）不占音节
            codes = m[2].split(' ')
            if len(chars) == len(codes):
                new = ' '.join(c[:3] + (aux_of(ch, c[:2]) if ch in AUX else c[3:]) for ch, c in zip(chars, codes))
                if new != m[2]: stat['词条改码'] += 1
                l = f'{m[1]}\t{new}{m[3] or ""}'
            else: stat['词条字数与码数不符（原样）'] += 1
        out.append(l)
    p.write_text('\n'.join(out), encoding='utf-8')

# ---- Lua 辅码库 zrmdb.txt ----
p = OUT / 'lua/zrmdb.txt'; out = []
for l in p.read_text(encoding='utf-8').split('\n'):
    t = l.split('\t')[0]
    out.append(f'{t}\t{" ".join(AUX[t])}' if t in AUX and '\t' in l else l)
p.write_text('\n'.join(out), encoding='utf-8')

# ---- 拆分提示（opencc）：夜桜字用夜桜拆分，其余字用魔然原拆分 ----
YSPLIT = {}
for l in open(SPLITS, encoding='utf-8-sig'):
    t, s = l.rstrip('\n').split('\t', 1); YSPLIT[t] = s.replace(' ＋ ', '＋')
tips = collections.OrderedDict()
for l in open(CHAI, encoding='utf-8'):
    if l.startswith('#') or '\t' not in l: continue
    x = l.rstrip('\n').split('\t')
    if len(x) >= 3 and x[0] not in AUX: tips[x[0]] = tips.get(x[0], '') + f'〔{x[2]}{x[1]}〕'
for t in AUX: tips[t] = ''.join(f'〔{YSPLIT[t]}·{a}〕' if n == 0 and t in YSPLIT else f'〔{a}〕' for n, a in enumerate(AUX[t]))   # 其余辅码是保留的旧拆法，不配拆分
(OUT / 'opencc/moran_chaifen.txt').write_text(''.join(f'{t}\t{s}\n' for t, s in tips.items()), encoding='utf-8')
(OUT / 'opencc/moran_chaifen.ocd2').unlink()
j = (OUT / 'opencc/moran_chaifen.json').read_text(encoding='utf-8')
assert j.count('"type": "ocd2",\n        "file": "moran_chaifen.ocd2"') == 1 and j.count('"file": "moran_chaifen.ocd2"') == 2, j
j = j.replace('"type": "ocd2",\n      "file": "moran_chaifen.ocd2"', '"type": "text",\n      "file": "moran_chaifen.txt"')
j = j.replace('"type": "ocd2",\n        "file": "moran_chaifen.ocd2"', '"type": "text",\n        "file": "moran_chaifen.txt"')
assert 'ocd2' not in j, j
(OUT / 'opencc/moran_chaifen.json').write_text(j, encoding='utf-8')

# ---- 字词定长码表：用户自己的表，只换单字 ----
subprocess.run([str(ROOT / '.venv/bin/python'), str(ROOT / 'yozakura/定制/make_custom.py'), str(FIXED), str(OUT / 'moran_fixed_simp.dict.yaml')], check=True)

print(OUT, dict(stat), '夜桜辅码字', len(AUX), '拆分提示', len(tips))
