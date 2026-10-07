"""把当前码表实时更新到作者自己的 Rime（~/Library/Rime），改完一条反馈就跑一次。
1. 字词表/综合表（release/make_ciku.py）
2. 调频方案 yeying_tune：码表（rime/make_dict.py，版本号用时间戳）＋ 反查数据
3. 夜莺整句 yeying_sentence：无一简表 → 整句包 → 反查数据
4. 正式三方案 yeying_v5 / yeying_shape / yeying_single：搭台 → 夜莺构建工具出包（不跑验证，发布时才验证）
5. 只复制有变化的文件到 ~/Library/Rime，然后让鼠须管重新部署；~/Downloads 里的单字表、字词表、综合表一并刷新
上次装进去的单字表存在 ~/.cache/yeying-local/installed_普通单字表.txt（make_dict 要用它区分附加条目）；首次取 git 标签 v3.0 的表。
用法：.venv/bin/python release/update_local_rime.py
"""
import datetime, filecmp, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / '.venv/bin/python')
RIME = Path.home() / 'Library/Rime'
DL = Path.home() / 'Downloads'
STATE = Path.home() / '.cache/yeying-local'
STAGE = Path.home() / '.cache/yeying30-build'
TABLES = ROOT / 'release/tables'
PLAIN = TABLES / '夜莺3.0_NB46_普通单字表.txt'
SENT_PKG = DL / '虎整句-Rime-20261001-D89-r3-四档纠错瓢虫版'
NOYJ = DL / '夜莺3.0_NB46_无一简试验版_普通单字表.txt'
run = lambda *a, **k: subprocess.run([str(x) for x in a], check=True, **k)
quiet = dict(stdout=subprocess.DEVNULL)
STATE.mkdir(parents=True, exist_ok=True)
installed = STATE / 'installed_普通单字表.txt'
if not installed.exists():
    installed.write_bytes(subprocess.run(['git', '-C', str(ROOT), 'show', f'v3.0:{PLAIN.relative_to(ROOT)}'], check=True, capture_output=True).stdout)

print('1/5 字词表'); run(PY, ROOT / 'release/make_ciku.py', **quiet)
print('2/5 调频方案')
run(PY, ROOT / 'rime/make_dict.py', installed, PLAIN, 'local-' + datetime.datetime.now().strftime('%Y%m%d%H%M'), **quiet)
run(PY, ROOT / 'rime/make_lookup.py', PLAIN, ROOT / 'rime/Rime/lua/yeying_tune_lookup_data.lua', '1', **quiet)
print('3/5 整句方案')
tmp = STATE / 'work'; shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir()
run(PY, ROOT / 'release/no_yijian.py', PLAIN, tmp / 'noyj', **quiet)
shutil.copy(tmp / 'noyj/C升二简且抢三码_普通单字表.txt', NOYJ)
run(PY, ROOT / 'rime/sentence/build_sentence.py', SENT_PKG, NOYJ, tmp / 'sentence', **quiet)
run(PY, ROOT / 'rime/make_lookup.py', tmp / 'sentence/yeying_sentence.codes.txt', ROOT / 'rime/Rime/lua/yeying_sentence_lookup_data.lua', '0', **quiet)
print('4/5 正式三方案（构建，不验证）')
run(PY, ROOT / 'release/stage_nightingale30.py', **quiet)
run(PY, STAGE / 'tools/maintenance/build_mac.py', '--root', STAGE, stdout=open(STAGE / 'build.log', 'w'), stderr=subprocess.STDOUT)
print('5/5 安装')
SKIP = ('.md', '.example')
changed = []


def install(src_dir, names=None):
    for f in sorted(Path(src_dir).rglob('*')):
        rel = f.relative_to(src_dir)
        if not f.is_file() or f.name.endswith(SKIP) or f.name.startswith('LICENSE') or f.name == 'manifest.json' or 'models' in rel.parts:
            continue
        if names is not None and str(rel) not in names:
            continue
        dst = RIME / rel
        if not dst.exists() or not filecmp.cmp(f, dst, shallow=False):
            dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, dst); changed.append(str(rel))


for d in ('release-dual', 'release-single'):
    install(STAGE / '夜莺3.0/产物/mac' / d)
install(ROOT / 'rime/Rime', {'yeying_tune.dict.yaml', 'lua/yeying_tune_lookup_data.lua', 'lua/yeying_sentence_lookup_data.lua'})
install(tmp / 'sentence')
shutil.copy(PLAIN, installed)
for name in ('普通单字表', '字词表', '综合表', '综合表_码前'):
    shutil.copy(TABLES / f'夜莺3.0_NB46_{name}.txt', DL / f'夜莺3.0_NB46_{name}.txt')
(DL / '夜莺3.0_NB46_普通单字表_码前.txt').write_text(
    ''.join(f'{c}\t{t}\n' for t, c in (l.rstrip('\n').split('\t')[:2] for l in open(PLAIN, encoding='utf-8-sig') if '\t' in l)), encoding='utf-8')
print('更新文件：', ' '.join(changed) or '无')
if changed:
    run('/Library/Input Methods/Squirrel.app/Contents/MacOS/Squirrel', '--reload')
    if any('sentence' in c for c in changed):
        print('整句方案的码表变了：需要退出并重启鼠须管才会生效（--reload 不会重载整句模型数据）。')
