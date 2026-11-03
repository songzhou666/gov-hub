# -*- coding: utf-8 -*-
"""gov-hub CLI：init（范围确认关）/ check / status。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from . import core


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.root or ".").resolve()
    if core.load_config(root) is not None:
        print(f"[SKIP] {core.config_path(root)} 已存在——范围已声明，不重新推断。")
        print("       如需变更范围，直接编辑该文件后运行 check。")
        return 0
    cands = core.detect_candidates(root)
    print("检测到候选范围（启发式仅供选择，确认后才固化）：\n")
    for i, c in enumerate(cands, 1):
        print(f"  [{i}] {c['path']}\n      {c['reason']}")
    print(f"  [0] {root}（当前目录，无标记依赖）")
    try:
        pick = input("\n选择主工作区编号 [默认 0]: ").strip() or "0"
    except EOFError:
        pick = "0"
    if pick.isdigit() and 1 <= int(pick) <= len(cands):
        main = cands[int(pick) - 1]["path"]
    else:
        main = str(root)
    extra = input("旁挂目录（可选，逗号分隔，相对主工作区）: ").strip()
    cfg = core.default_config()
    cfg["scope"]["roots"] = [main] + [x.strip() for x in extra.split(",") if x.strip()]
    path = core.write_config(root, cfg)
    print(f"\n已固化范围声明 → {path}（scope 指纹 {core.fingerprint(cfg, root)}）")
    print("下一步：在主根创建 registry.yaml（参考 seeds/sample-workspace），然后运行 check。")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    root = Path(args.root or ".").resolve()
    cfg = core.load_config(root)
    if cfg is None:
        print(f"[FATAL] 未找到 {core.CONFIG_NAME} —— 范围未声明。先运行 init。")
        return 2
    result = core.check_registry(root, cfg)
    st = result["stats"]
    print(f"登记表 v{st['version']} · updated {st['updated']} · {st['total']} 条")
    for t, n in sorted(st["by_type"].items()):
        print(f"  {t}: {n}")
    for p in result["problems"]:
        print(f"  [FAIL] {p}")
    print("结果：", "通过 ✅" if result["ok"] else "不通过 ❌")
    if args.json:
        print(json.dumps({**result, "fingerprint": core.fingerprint(cfg, root)},
                         ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def cmd_status(args: argparse.Namespace) -> int:
    root = Path(args.root or ".").resolve()
    cfg = core.load_config(root)
    if cfg is None:
        print(f"[FATAL] 未找到 {core.CONFIG_NAME} —— 范围未声明。先运行 init。")
        return 2
    state = core.lamps(root, cfg)
    for name, d in state["lamps"].items():
        print(f"  {name:9s} [{d['level']:6s}] {d['detail']}")
    for g in state["gaps"]:
        print(f"  缺口: {g['dir']}（{g['mtime']}）→ 登记 or 归档")
    print(f"  scope 指纹 {state['fingerprint']} · layout {cfg['layout']}")
    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0 if state["check"]["ok"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="govhub", description="gov-hub 治理骨架 CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn, help_ in [("init", cmd_init, "范围确认关：探测候选并固化 gov-hub.yaml"),
                            ("check", cmd_check, "机检：登记表 ↔ 磁盘一致性"),
                            ("status", cmd_status, "四段健康灯 + 回灌缺口")]:
        p = sub.add_parser(name, help=help_)
        p.add_argument("--root", default=".", help="工作区根（含 gov-hub.yaml 的目录）")
        p.add_argument("--json", action="store_true")
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    return args.fn(args)
