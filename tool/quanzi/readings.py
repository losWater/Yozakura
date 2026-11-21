"""全字版的读音：魔然为主（tools/data/chars.txt，约 8.4 万字，带简体字频）；魔然没有的字取冰雪拼音（snow_pinyin.dict.yaml，作者 2026-11-21 加）。
冰雪拼音里 mou3 是“读音不详”的占位：只有 mou 的字不收，有别的读音时去掉 mou；ê 等换不成双拼的读音不收。
load() → (字 → [无调拼音，ü 作 v]，字 → 字频)
"""
import collections, re
from pathlib import Path
MORAN = Path.home() / '.cache/auxcmp/moran/tools/data/chars.txt'
SNOW = Path.home() / '.cache/chai-data/snow_pinyin.dict.yaml'


def load():
    reads, freq = collections.defaultdict(list), collections.Counter()
    for l in open(MORAN, encoding='utf-8'):
        p = l.rstrip('\n').split('\t')
        if l.startswith('#') or len(p) < 2 or len(p[0]) != 1 or not p[1]: continue
        if p[1] not in reads[p[0]]: reads[p[0]].append(p[1])
        freq[p[0]] += int(p[3]) if len(p) > 3 and p[3].isdigit() else 0
    snow, sfreq, body = collections.defaultdict(list), collections.Counter(), False
    for l in open(SNOW, encoding='utf-8'):
        if l.startswith('...'): body = True; continue
        if not body or l.startswith('#') or '\t' not in l: continue
        p = l.rstrip('\n').split('\t')
        py = re.sub(r'[1-5]$', '', p[1]).replace('ü', 'v')
        if len(p[0]) != 1 or p[0] in reads or not re.fullmatch(r'[a-z]+', py): continue
        if py not in snow[p[0]]: snow[p[0]].append(py)
        sfreq[p[0]] += int(p[2]) if len(p) > 2 and p[2].isdigit() else 0
    for c, ps in snow.items():
        ps = [x for x in ps if x != 'mou'] or []
        if ps: reads[c] = ps; freq[c] = sfreq[c]
    return reads, freq
