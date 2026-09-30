"""第二轮排位赛：64 强在 set1–set5 五套新句子上各实打一次，取实打分平均；理论分沿用第一轮。
总分 = 0.7 × 理论分 + 0.3 × 五次实打分平均。尺子与第一轮同口径、同冻结尺子。
用法：python tournament/round2.py [typed|full]"""
import json, sys, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'eval')); sys.path.insert(0, str(ROOT / 'tournament'))
import score as SC
import rank as RK
import evaluate as EV
from make_table import build
import type_sim

T = ROOT / 'runs/formal'


def main(mode):
    r1 = json.load(open(T / f'round1_{mode}.json', encoding='utf-8'))
    scale = json.load(open(ROOT / f'eval/calib/scale_{mode}.json', encoding='utf-8'))['尺子']
    sets = []
    for k in range(1, 6):
        sets.append((json.load(open(ROOT / f'eval/sentences/set{k}.json', encoding='utf-8')),
                     json.load(open(ROOT / f'eval/sentences/set{k}.readings.json', encoding='utf-8'))))
    rows = []
    for jid in r1['64强']:
        ev = json.load(open(T / jid / 'eval.json', encoding='utf-8'))
        out = sorted((T / jid).glob('output-*'))[0]
        items = build(EV.EL, str(out / 'code.txt'))
        its = items if mode == 'typed' else EV.full_only(items, out / 'code.txt')
        book = type_sim.code_book(its)
        typing_scores, details = [], []
        for S, R in sets:
            t = type_sim.simulate(book, S, R)
            flat = RK.flatten({**ev, mode: {**ev[mode], 'type': t}}, mode)
            s = SC.score(flat, scale)
            typing_scores.append(s['实打分'])
            theory = s['理论分']
            details.append({k: v for k, v in t.items() if k not in ('热力', '最忙键')})
        avg = statistics.mean(typing_scores)
        rows.append({'id': jid, '理论分': theory, '实打五次': typing_scores, '实打平均': avg,
                     '实打标准差': statistics.pstdev(typing_scores), '总分': 0.7 * theory + 0.3 * avg,
                     '第一轮总分': next(r['总分'] for r in r1['明细'] if r['id'] == jid)})
        print(jid, round(rows[-1]['总分'], 2), flush=True)
    rows.sort(key=lambda r: -r['总分'])
    json.dump({'口径': mode, '排名': rows}, open(T / f'round2_{mode}.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('冠军', rows[0]['id'], round(rows[0]['总分'], 2), '；前五', [(r['id'], round(r['总分'], 2)) for r in rows[:5]])


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'typed')
