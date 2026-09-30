"""把引擎输出 code.txt 转为单字码表（字\\t码，按 码→候选位→元素序 排序），供形码盒子与实打使用。
用法：python eval/make_table.py <元素表 elements.yaml> <code.txt> <输出 tsv>"""
import sys, yaml

def build(elements, code_txt):
    E = yaml.safe_load(open(elements, encoding='utf-8'))
    n = sum(1 for e in E if e['拼音'] != 'reserved')
    rows = [l.rstrip('\n').split('\t') for l in open(code_txt, encoding='utf-8')][:n]
    items = []
    for i, r in enumerate(rows):
        full, fr, short, sr = r[1], int(r[2]), r[3], int(r[4])
        items.append((full, fr, i, r[0], E[i]['拼音']))
        if short and short != full:
            items.append((short, sr, i, r[0], E[i]['拼音']))
    items.sort()
    return items

if __name__ == '__main__':
    items = build(sys.argv[1], sys.argv[2])
    with open(sys.argv[3], 'w', encoding='utf-8') as f:
        for code, rank, i, ch, py in items:
            f.write(f'{ch}\t{code}\n')
    print('条目', len(items))
