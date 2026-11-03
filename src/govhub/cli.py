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


def _ask(prompt: str, default: str = "") -> str:
    """交互提问；非交互环境（管道/agent 调用）EOF 时静默取默认值。"""
    try:
        raw = input(prompt).strip()
        return raw or default
    except EOFError:
        return default


def explain_text(root: Path) -> str:
    """向用户展示意图：做什么、建什么、不碰什么、怎么卸。"""
    cands = core.detect_candidates(root)
    hint = cands[0]["path"] if cands else str(root)
    return f"""\n【gov-hub 初始化说明】（如需再看: python govhub.py init --explain）

它解决什么问题：agent 在项目里经常不知道该读哪个文件，做完活产出也没人知道。
gov-hub 给项目装一张机读路由表：agent 动手前先查表直达权威文件，收尾时产出自动提醒登记。

初始化只做两件事（一次，约 1 分钟）：
  1. 写 gov-hub.yaml   —— 声明治理范围（探测到候选: {hint}），你确认后才生效
  2. 写 registry.yaml  —— 路由表骨架，含 2 条示例条目，你填真实资产后删除示例

三条边界（写进代码，不靠承诺）：
  - 只新增文件，不改写、不删除你的任何既有文件
  - 所有命令只读你的项目内容，不联网、不上传
  - 产出索引 .govhub/ 可随时删，自动重建

后悔成本：删除上面三个文件 = 完全卸载，项目恢复原样。
不做会怎样：不装没有任何影响，agent 退回蛮力翻文件的方式。\n"""


def _gate(root: Path) -> int | None:
    """入口闸：已拒绝 → 静默退出；未声明 → 展示意图 + 引导一次性询问。"""
    if core.declined(root):
        print(f"[MUTED] 本区已声明不启用治理（{core.DECLINE_NAME}）。"
              f"不再提示；用户反悔可删除该文件或运行 init --main . --override。")
        return 2
    if core.load_config(root) is None:
        print("[UNDECLARED] 本区未声明治理范围。向用户展示以下说明后询问一次"
              "（同意 → init --main <路径>；拒绝/跳过 → init --decline，之后不再问）：")
        print(explain_text(root))
        return 2
    return None


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.root or ".").resolve()
    if args.explain:
        print(explain_text(root))
        return 0
    if args.decline:
        (root / core.DECLINE_NAME).write_text(
            f"declined: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"note: 用户拒绝或跳过初始化；治理命令对本区静默。\n", encoding="utf-8")
        print(f"已记录拒绝声明 → {root / core.DECLINE_NAME}")
        print("治理命令对本区进入静默模式；反悔时删除该文件或运行 init --main . --override。")
        return 0
    if core.declined(root) and not args.override:
        print(f"[MUTED] 本区已声明不启用治理。如确要启用，加 --override 覆盖拒绝标记。")
        return 2
    if args.override and core.declined(root):
        (root / core.DECLINE_NAME).unlink()
        print("已移除拒绝标记。")
    if core.load_config(root) is not None:
        print(f"[SKIP] {core.config_path(root)} 已存在——范围已声明，不重新推断。")
        print("       如需变更范围，直接编辑该文件后运行 check。")
        return 0
    if args.main:  # 显式参数路径：不进交互，适合 agent / 脚本调用
        main = Path(args.main if Path(args.main).is_absolute()
                    else (root / args.main)).resolve()
        extras = [x.strip() for x in (args.extra or "").split(",") if x.strip()]
    else:  # 交互路径：探测候选，人工选择
        cands = core.detect_candidates(root)
        print("检测到候选范围（启发式仅供选择，确认后才固化）：\n")
        for i, c in enumerate(cands, 1):
            print(f"  [{i}] {c['path']}\n      {c['reason']}")
        print(f"  [0] {root}（当前目录，无标记依赖）")
        pick = _ask("\n选择主工作区编号 [默认 0]: ", "0")
        if pick.isdigit() and 1 <= int(pick) <= len(cands):
            main = Path(cands[int(pick) - 1]["path"])
        else:
            main = root
        extras = [x.strip() for x in _ask("旁挂目录（可选，逗号分隔，相对主工作区）: ").split(",") if x.strip()]
    cfg = core.default_config()
    cfg["scope"]["roots"] = [str(main)] + [
        x if Path(x).is_absolute() else str((main / x).resolve()) for x in extras]
    path = core.write_config(root, cfg)
    print(f"\n已固化范围声明 → {path}（scope 指纹 {core.fingerprint(cfg, root)}）")
    reg_path, created = _write_registry_skeleton(main)
    print(f"登记表 → {reg_path}" + ("（已生成骨架，含两条示例条目）" if created
                                  else "（已存在，未覆盖）"))
    print("下一步：把示例条目改成你的真实资产，然后依次运行 check 与 status。")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    root = Path(args.root or ".").resolve()
    if (g := _gate(root)) is not None:
        return g
    cfg = core.load_config(root)
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
    if (g := _gate(root)) is not None:
        return g
    cfg = core.load_config(root)
    index = core.load_index(root, cfg)
    note = "（索引曾 stale，已自动重建）" if index.get("rebuilt") else ""
    if core.registry_changed(root, cfg, index):
        index = core.build_index(root, cfg)
        note = "（登记表内容有变化，索引已重建）"
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
    if (g := _gate(root)) is not None:
        return g
    cfg = core.load_config(root)
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
    p.add_argument("--main", default="", help="显式指定主工作区（跳过交互，agent/脚本用）")
    p.add_argument("--extra", default="", help="旁挂目录，逗号分隔（配合 --main）")
    p.add_argument("--explain", action="store_true",
                   help="只打印初始化意图说明，不做任何操作")
    p.add_argument("--decline", action="store_true",
                   help="记录用户拒绝：写 gov-hub.declined，治理命令此后静默")
    p.add_argument("--override", action="store_true",
                   help="覆盖已有拒绝标记，走正常初始化")
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
