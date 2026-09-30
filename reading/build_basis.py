"""生成夜桜字音基准：整字总频沿用 2.0（自然频率之和），多音字各读音份额换为语料实测。
规则（作者 2026-09-30 定）：
- 词内读音以词典（pypinyin）为准 = 规范音；单字成词以 g2pW 为准。
- 口语异读：仅限文白异读白名单字，且 g2pW 在词内给出的正是其白读音时，计入“口语频率”，退火权重另设（默认 0.5）。
  （按分歧率自动选会混入 g2pW 错标，如 首都→dou、大厦→xia、通缉→qi，故改白名单。）
- 著：只用现代体裁（名著中 著=着 的旧用法会扭曲份额）。
- 语料出现 <30 次的字保留 2.0 份额。音码改为自然码。"""
import json, sys, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'reading')); sys.path.insert(0, str(ROOT / 'lib'))
from annotate import READ, BASE
from shuangpin import encode

G = 'news wiki zhihu forum webnovel classic'.split()
MODERN_ONLY = {'著'}
MIN_OCC, COLLOQ_MIN_N = 30, 10
TW = {('和', 'han'): 'he'}
BAIDU = {'血': 'xie', '熟': 'shou', '薄': 'bao', '剥': 'bao', '削': 'xiao', '塞': 'se', '色': 'shai',
         '落': 'lao', '露': 'lou', '嚼': 'jiao', '壳': 'qiao', '择': 'zhai', '给': 'ji', '伯': 'bai'}

P = {g: json.load(open(ROOT / f'reading/out/{g}.pass1.json', encoding='utf-8')) for g in G}
lab = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
val = collections.defaultdict(collections.Counter)      # 字 -> Counter{('agree'|reading_g2pw): n}
for l in open(ROOT / 'reading/out/pass2.jsonl', encoding='utf-8'):
    j = json.loads(l)
    y = TW.get((j['c'], j['g2pw']), j['g2pw'])
    if y not in READ[j['c']]:
        continue
    if j['k'] == 'single':
        lab[j['g']][j['c']][y] += 1
    elif j['dict'] in READ[j['c']]:
        val[j['c']]['=' if y == j['dict'] else y] += 1

old_share, old_total = collections.defaultdict(dict), collections.Counter()
for r in BASE:
    old_total[r['字']] += r['自然频率'] or 0
for r in BASE:
    t = old_total[r['字']]
    old_share[r['字']][r['拼音']] = (r['自然频率'] or 0) / t if t else 0

inword, single = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
for g in G:
    for c, d in P[g]['inword'].items():
        if c in MODERN_ONLY and g == 'classic':
            continue
        for s, n in d.items():
            if s in READ[c]:
                inword[c][s] += n
    for c, n in P[g]['single_n'].items():
        if c in MODERN_ONLY and g == 'classic':
            continue
        smp = lab[g][c] or collections.Counter({k: v for k, v in old_share[c].items() if v > 0})
        t = sum(smp.values())
        for s, k in smp.items():
            single[c][s] += n * k / t

out, log = [], collections.Counter()
for r in BASE:
    c, s = r['字'], r['拼音']
    total = old_total[c]
    occ = sum(inword[c].values()) + sum(single[c].values())
    row = dict(字=c, 拼音=s, 音码=encode(s, 'ziranma'), 小鹤音码=r['音码'], 旧自然频率=r['自然频率'])
    if len(READ[c]) < 2:
        row.update(自然频率=r['自然频率'], 来源='单音字')
    elif occ < MIN_OCC:
        row.update(自然频率=r['自然频率'], 来源='语料不足沿用2.0'); log['语料不足'] += 1
    else:
        share = (inword[c][s] + single[c][s]) / occ
        row.update(自然频率=total * share, 来源='语料实测'); log['语料实测'] += 1
        v = val[c]; nv = sum(v.values())
        if BAIDU.get(c) == s and nv >= COLLOQ_MIN_N and v[s]:
            iw_share = sum(inword[c].values()) / occ
            row['口语频率'] = total * iw_share * v[s] / nv
            log['口语异读'] += 1
    out.append(row)

dst = ROOT / 'data/inputs/夜桜字音基准.json'
json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('条目', len(out), dict(log))
print('口语异读：', [(r['字'], r['拼音'], round(r['口语频率'], 1)) for r in out if '口语频率' in r])
for ch in '的了地都着长谁熟血著':
    print(ch, [(r['拼音'], round(r['旧自然频率'], 1), round(r['自然频率'], 1), r.get('口语频率') and round(r['口语频率'], 1)) for r in out if r['字'] == ch])
