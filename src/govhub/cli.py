# -*- coding: utf-8 -*-
"""gov-hub CLI：init（范围确认关 + 登记表骨架）/ check / lookup / status。"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from . import core

REGISTRY_TEMPLATE = """# gov-hub 登记表：关键词 -> 资产单元 -> 权威文件 的机读路由。
# authority: canonical（SSOT）| derived（派生）| generated（可重建，永不作权威引用）
version: 1
updated: '{today}'
entries:
- id: rule.example          # 类型_主题；查这条用: govhub lookup example
  type: rule
  title: 示例规则（改我）
  path: rules/example.md    # 相对主工作区根；填好后跑 govhub check 验证
  keywords: [示例, example]
  answers: 这条资产能回答什么问题（一行）
  authority: canonical
  updated: '{today}'
- id: asset.example-doc
  type: asset
  title: 示例文档（删我）
  path: docs/example.md
  keywords: [文档]
  answers: 第二条示例，建好真实条目后删除本条
  authority: canonical
  updated: '{today}'
"""


def _write_registry_skeleton(main_root: Path) -> tuple[Path, bool]:
    """返回 (路径, 是否新建)。已有登记表绝不覆盖。"""
    path = main_root / core.REGISTRY_NAME
    if path.exists():
        return path, False
    path.write_text(REGISTRY_TEMPLATE.replace("{today}", datetime.now().strftime("%Y-%m-%d")),
                    encoding="utf-8")
    return path, True


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
        main = Path(cands[int(pick) - 1]["path"])
    else:
        main = root
    extra = input("旁挂目录（可选，逗号分隔，相对主工作区）: ").strip()
    cfg = core.default_config()
    cfg["scope"]["roots"] = [str(main)] + [
        x.strip() if Path(x.strip()).is_absolute() else str((main / x.strip()).resolve())
        for x in extra.split(",") if x.strip()]
    path = core.write_config(root, cfg)
    print(f"\n已固化范围声明 → {path}（scope 指纹 {core.fingerprint(cfg, root)}）")
    reg_path, created = _write_registry_skeleton(main)
    print(f"登记表 → {reg_path}" + ("（已生成骨架，含两条示例条目）" if created
                                  else "（已存在，未覆盖）"))
    print("下一步：把示例条目改成你的真实资产，然后依次运行 check 与 status。")
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
    if result["ok"]:
        index = core.build_index(root, cfg)
        print(f"检索索引已同步（.govhub/index.json · 指纹 {index['fingerprint']}）")
    if args.json:
        print(json.dumps({**result, "fingerprint": core.fingerprint(cfg, root)},
                         ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def cmd_lookup(args: argparse.Namespace) -> int:
    root = Path(args.root or ".").resolve()
    cfg = core.load_config(root)
    if cfg is None:
        print(f"[FATAL] 未找到 {core.CONFIG_NAME} —— 范围未声明。先运行 init。")
        return 2
    index = core.load_index(root, cfg)
    note = "（索引曾 stale，已自动重建）" if index.get("rebuilt") else ""
    if core.registry_changed(root, cfg, index):
        index = core.build_index(root, cfg)
        note = "（登记表 updated 有变化，索引已重建）"
    hits = core.search(index, args.terms, limit=args.limit)
    if not hits:
        print(f"未命中。试试登记表里已有的关键词，或先 check 同步索引。{note}")
        return 1
    for e in hits:
        print(f"  [{e['score']:5}] {e['id']} · {e['authority']} · {e['path']}")
        print(f"         {e['title']} —— {e['answers']}")
    print(f"共 {len(hits)} 条{note}")
    if args.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = Path(args.root or ".").resolve()
    cfg = core.load_config(root)
    if cfg is None:
        print(f"[FATAL] 未找到 {core.CONFIG_NAME} —— 范围未声明。先运行 init。")
        return 2
    index = core.load_index(root, cfg)
    state = core.lamps(root, cfg)
    for name, d in state["lamps"].items():
        print(f"  {name:9s} [{d['level']:6s}] {d['detail']}")
    for g in state["gaps"]:
        print(f"  缺口: {g['dir']}（{g['mtime']}）→ 登记 or 归档")
    fresh = "同步" if not core.registry_changed(root, cfg, index) else "登记表有更新，check 后同步"
    print(f"  scope 指纹 {state['fingerprint']} · layout {cfg['layout']} · 索引{fresh}")
    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0 if state["check"]["ok"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="govhub", description="gov-hub 治理骨架 CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="范围确认关：探测候选并固化 gov-hub.yaml + 登记表骨架")
    p.add_argument("--root", default=".", help="工作区根")
    p.set_defaults(fn=cmd_init)
    p = sub.add_parser("check", help="机检：登记表 ↔ 磁盘一致性；通过则同步检索索引")
    p.add_argument("--root", default=".")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("lookup", help="关键词 → 资产单元 → 权威文件")
    p.add_argument("terms", nargs="+", help="一个或多个关键词")
    p.add_argument("--root", default=".")
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_lookup)
    p = sub.add_parser("status", help="四段健康灯 + 回灌缺口")
    p.add_argument("--root", default=".")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_status)
    args = ap.parse_args()
    return args.fn(args)
