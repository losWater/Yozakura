"""更新日志附录：上一版（git 标签 v<上一版>）与当前字词表逐条比对，全部列出，写进 release/更新日志/夜莺<版本>.md 的“## 附录”之后。
- 单字码变化：每个字的码（含一二三简与全码）有任何增减都列出，旧 → 新，按字频排序
- 首选变化：每个码位的第一候选有变化都列出，旧 → 新，按码排序
- 新增、删除的词条
用法：.venv/bin/python release/changelog_appendix.py   （release/publish.py 第一段会自动调用）
"""
import collections, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'release'))
from config import C


def rows(text):
    return [tuple(l.rstrip('\r\n').split('\t')[:2]) for l in text.splitlines() if '\t' in l]


def previous():
    for p in ('release/tables/字词表.txt', 'release/tables/夜莺3.0_NB46_字词表.txt'):   # 3.0 标签里还是旧文件名
        r = subprocess.run(['git', '-C', str(ROOT), 'show', f'v{C.PREV}:{p}'], capture_output=True, text=True)
        if r.returncode == 0: return rows(r.stdout)
    raise FileNotFoundError(f'v{C.PREV} 的字词表')


old, new = previous(), rows(C.T('字词表.txt').read_text(encoding='utf-8'))
rank = {l.split('\t')[0]: i for i, l in enumerate(open(ROOT / 'eval/box/默认字频.txt', encoding='utf-8-sig'), 1)}


def by(rows_, single):
    d = collections.defaultdict(list)
    for t, c in rows_:
        if (len(t) == 1) == single: d[t].append(c)
    return d


def slots(rows_):
    d = collections.defaultdict(list)
    for t, c in rows_: d[c].append(t)
    return d


oc, nc = by(old, True), by(new, True)
key = lambda c: (len(c), c)
chars = sorted((t for t in set(oc) | set(nc) if sorted(oc.get(t, [])) != sorted(nc.get(t, []))), key=lambda t: (rank.get(t, 10**6), t))
os_, ns = slots(old), slots(new)
firsts = sorted((c for c in set(os_) | set(ns) if (os_.get(c) or [None])[0] != (ns.get(c) or [None])[0]), key=key)
ow, nw = {(t, c) for t, c in old if len(t) > 1}, {(t, c) for t, c in new if len(t) > 1}
added, removed = sorted(nw - ow, key=lambda x: key(x[1])), sorted(ow - nw, key=lambda x: key(x[1]))
fmt = lambda cs: ' '.join(sorted(cs, key=key)) or '（无）'
out = [f'### 单字码变化（{len(chars)} 字）', '']
out += [f'- {t}：{fmt(oc.get(t, []))} → {fmt(nc.get(t, []))}' for t in chars]
out += ['', f'### 首选变化（{len(firsts)} 个码位）', '']
out += [f'- {c}：{(os_.get(c) or ["（空）"])[0]} → {(ns.get(c) or ["（空）"])[0]}' for c in firsts]
out += ['', f'### 新增词条（{len(added)} 条）', '', '、'.join(f'{t} {c}' for t, c in added) + '。']
if removed:
    out += ['', f'### 删除词条（{len(removed)} 条）', '', '、'.join(f'{t} {c}' for t, c in removed) + '。']
md = C.CHANGELOG.read_text(encoding='utf-8')
head = md.split('\n## 附录\n', 1)[0]
intro = f'以下由 {C.PREV} 与 {C.V} 的字词表逐条比对生成，包含上面所有改动带来的全部变化。'
C.CHANGELOG.write_text(head.rstrip('\n') + '\n\n## 附录\n\n' + intro + '\n\n' + '\n'.join(out) + '\n', encoding='utf-8')
print(f'附录：单字码变化 {len(chars)} 字，首选变化 {len(firsts)} 码位，新增词条 {len(added)}，删除 {len(removed)}')
