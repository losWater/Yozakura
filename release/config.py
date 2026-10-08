"""发布配置（release/版本.json）的唯一入口：版本号、上一版、日期、文件名都从这里取，脚本里不写死版本。
from config import C  →  C.V（如 '3.1'）、C.PREV、C.NAME（'夜莺3.1'）、C.DATE（'2026-10-08'）、C.STAMP（'20261008'）、
C.LAYOUT、C.STAGE/C.MAC_OUT（Rime 搭台与产物目录）、C.T(名)（release/tables/ 下的正式表）、C.CHANGELOG（本版更新日志 md）、C.PRACTICE（练习对照）、C.UPGRADE、C.HISTORY。
日期默认取今天；环境变量 YZ_DATE=YYYY-MM-DD 可指定（重跑某次发布时用）。
"""
import datetime, json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class _C:
    def __init__(self):
        d = json.load(open(ROOT / 'release/版本.json', encoding='utf-8'))
        self.V, self.PREV, self.LAYOUT = d['版本'], d['上一版'], d['布局']
        self.NAME = f'夜莺{self.V}'
        self.DATE = os.environ.get('YZ_DATE') or datetime.date.today().isoformat()
        self.STAMP = self.DATE.replace('-', '')
        self.PRACTICE = d['练习对照']
        self.UPGRADE = d['升级说明']
        self.HISTORY = d['历史发布页']
        self.SOURCE = d['源码']
        self.RECORD = f"{self.SOURCE}/{d['维护记录']}"
        self.CHANGELOGS = sorted((ROOT / 'release/更新日志').glob('夜莺*.md'), key=lambda p: [int(x) for x in p.stem[2:].split('.')], reverse=True)
        self.CHANGELOG = ROOT / f'release/更新日志/夜莺{self.V}.md'
        self.TABLES = ROOT / 'release/tables'
        self.STAGE = Path.home() / '.cache/yeying-build'           # Rime 打包搭台目录（release/stage_rime.py）
        self.MAC_OUT = self.STAGE / f'{self.NAME}/产物/mac'           # 夜莺构建工具的 Mac 产物

    def T(self, name):
        return self.TABLES / name


C = _C()
