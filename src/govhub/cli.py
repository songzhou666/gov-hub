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
#
# 条目用命令登记最省事（agent 找到权威文件后立即调用）：
#   govhub add <文件> --keywords 词1,词2 --answers "这条能回答什么"
# 也可手工复制下面示例改：
# - id: rule.example
#   type: rule
#   title: 示例规则（改我）
#   path: rules/example.md
#   keywords: [示例, example]
#   answers: 这条资产能回答什么问题（一行）
#   authority: canonical
#   updated: '{today}'
version: 1
updated: '{today}'
entries: []
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
    """向用户展示意图：欢迎开场 → 要做什么 → 编号列痛点 → 完善后的收益 → 边界兜底。"""
    cands = core.detect_candidates(root)
    hint = cands[0]["path"] if cands else str(root)
    return f"""\n👋 欢迎使用 gov-hub 项目地图插件！

启用后，我们会为您的项目建立一张**项目地图**（标出项目里各文件的权威位置，
以及"它能回答什么问题"），方便您和 AI 的每次协作都更快、更省、更可靠。
（说明：它不是 AI 的对话记忆——地图就是两个普通文件，放在项目里、可随时查看修改。）

它主要解决以下常见问题：

  1. **AI 找文件靠瞎翻** —— 您问"这个功能的结论在哪"，AI 翻遍文件夹、读一堆
     无关内容还可能答错；启用后 AI 按地图一行直达权威文件。
  2. **干完活经验就丢** —— AI 的产出和结论散落在聊天记录里，换个会话就没了；
     启用后新产出的位置会被提醒补进地图，项目的经验留在项目里。
  3. **每次会话重复踩坑** —— 同一个问题换个 AI / 新会话又要从头找；
     启用后地图越用越全，新会话冷启动越来越快。

待地图完善后，您的每次对话都将：**提高检索速度、节约大量 tokens、
减少 AI 误读文件的出错率** —— 用得越久，收益越明显。

启用只需一次（约 1 分钟），我们会：
  1. 写入 gov-hub.yaml   —— 范围说明：AI 只在 {hint} 内活动，经您确认才生效
  2. 写入 registry.yaml  —— 项目地图文件（初始为空表，之后每找到一处权威内容就添一条）

📌 请放心（三条硬边界，写进代码，不靠承诺）：
  - 只新增这 2 个文件，不改写、不删除您的任何既有文件
  - 只读本机项目内容，不联网、不上传任何东西，不保存对话内容
  - 缓存目录 .govhub/ 可随时删除，自动重建

后悔成本：删掉这 2 个文件 = 完全卸载，项目恢复原样。
暂不启用：没有任何影响，一切维持现状。\n"""


def _gate(root: Path) -> int | None:
    """入口闸：已拒绝 → 静默退出；未声明 → 展示意图 + 引导一次性询问。"""
    if core.declined(root):
        print(f"[MUTED] 本区已声明不启用治理（{core.DECLINE_NAME}）。"
              f"不再提示；用户反悔可删除该文件或运行 init --main . --override。")
        return 2
    if core.load_config(root) is None:
        print("[UNDECLARED] 本区还没有\"项目地图\"（AI 找文件靠翻、产出不归档）。"
              "向用户展示以下说明后询问一次"
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
    print(f"登记表 → {reg_path}" + ("（已生成空表，等第一条真实条目）" if created
                                  else "（已存在，未覆盖）"))
    print("下一步：agent 找到权威文件时用 `add` 登记一条，然后依次运行 check 与 status。")
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
        core.record_trail(root, cfg, args.terms, None)  # 未命中也留迹：覆盖缺口的原料
        print(f"未命中。试试登记表里已有的关键词，或先 check 同步索引。{note}")
        return 1
    core.record_trail(root, cfg, args.terms, hits[0])  # 走过就留迹：起点→终点自动上地图
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


def cmd_suggest(args: argparse.Namespace) -> int:
    root = Path(args.root or ".").resolve()
    if (g := _gate(root)) is not None:
        return g
    cfg = core.load_config(root)
    props = core.suggest_proposals(root, cfg, min_hits=args.min)
    if not props:
        print("暂无提案：路线迹里还没有高频路线（同一目标被查到 ≥N 次才会提炼）。")
        return 0
    print(f"根据路线迹提炼出 {len(props)} 条登记提案（仅提案，确认后请手工改 registry.yaml）：\n")
    for p in props:
        print(f"[{p['kind']}] {p['id']} · {p['path']}")
        print(f"  依据：被查 {p["hits"]} 次，查法：{p['suggest_keywords']}")
        print(f"  建议 YAML：\n{p['yaml']}\n")
    if args.json:
        print(json.dumps(props, ensure_ascii=False, indent=2))
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    """登记一条资产（单命令，免手改 YAML）：agent 找到权威文件后立即调用。"""
    root = Path(args.root or ".").resolve()
    if (g := _gate(root)) is not None:
        return g
    cfg = core.load_config(root)
    main = core.resolve_root(root, cfg["scope"]["roots"][0])
    target = Path(args.path)
    if not target.is_absolute():
        target = main / target
    target = target.resolve()
    if not target.exists():
        print(f"[FAIL] 文件不存在：{target}")
        return 1
    try:
        rel = target.relative_to(main).as_posix()
    except ValueError:
        print(f"[FAIL] 不在主工作区 {main} 内（scope 外的文件不登记）：{target}")
        return 1
    reg_path = main / core.REGISTRY_NAME
    text = reg_path.read_text(encoding="utf-8")
    old_text = text
    reg = core.load_registry(root, cfg)
    norm = {str(e.get("path", "")).strip().replace("\\", "/") for e in reg["entries"]}
    if rel in norm:
        print(f"[跳过] 该文件已在登记表里：{rel}（要补关键词请直接编辑该条目）")
        return 0
    stem = target.stem
    eid = args.id.strip()
    if not eid:
        slug = "".join(ch if ch.isalnum() else "-" for ch in stem.lower()).strip("-")
        slug = "-".join(x for x in slug.split("-") if x)
        if not slug or not slug.isascii():
            import hashlib
            slug = "doc-" + hashlib.sha1(rel.encode("utf-8")).hexdigest()[:8]
        eid = f"{args.type}.{slug}"
    known_ids = {str(e.get("id")) for e in reg["entries"]}
    if eid in known_ids:
        import hashlib
        eid = f"{eid}-{hashlib.sha1(rel.encode('utf-8')).hexdigest()[:4]}"
    kws = [k.strip() for k in args.keywords.replace("，", ",").split(",") if k.strip()] or [stem]
    today = datetime.now().strftime("%Y-%m-%d")
    block = (f"- id: {eid}\n"
             f"  type: {args.type}\n"
             f"  title: {args.title or stem}\n"
             f"  path: {rel}\n"
             f"  keywords: [{', '.join(kws)}]\n"
             f"  answers: {args.answers or '（待补：这条能回答什么问题）'}\n"
             f"  authority: {args.authority}\n"
             f"  updated: '{today}'\n")
    if not text.endswith("\n"):
        text += "\n"
    import re as _re
    empty_entries = _re.search(r"^entries:\s*\[\s*\]\s*$", text, _re.M)
    if empty_entries:  # 空表：把 entries: [] 换成 entries: + 首条，避免 YAML 结构冲突
        start, end = empty_entries.span()
        text = text[:start] + "entries:\n" + block + text[end:].lstrip("\n")
    else:
        text += block
    reg_path.write_text(text, encoding="utf-8")
    result = core.check_registry(root, cfg)
    if not result["ok"]:
        reg_path.write_text(old_text, encoding="utf-8")  # 回滚，不留坏登记表
        print("[FAIL] 登记后机检不通过，已回滚：")
        for p in result["problems"]:
            print(f"  {p}")
        return 1
    core.build_index(root, cfg)
    print(f"已登记 → {eid}")
    print(f"  {rel}")
    print(f"  keywords: {kws} · authority: {args.authority}")
    print("机检通过 ✅ 索引已同步。")
    return 0


def _cli_path() -> str:
    """本 CLI 的可执行入口（供写进 AGENTS.md 的命令行）。"""
    return str(Path(__file__).resolve().parents[2] / "govhub.py")


def cmd_attach(args: argparse.Namespace) -> int:
    """把入口块写进 AGENTS.md（项目级或用户级）——标记块、幂等、可 detach 精确还原。

    不加入口闸：入口块本身就是给"尚未声明该区"的会话用的（块内自带条件句），
    若在此处要求先 init，则未声明区永远拿不到入口。
    """
    root = Path(args.root or ".").resolve()
    scope = args.scope
    target = Path(args.file) if args.file else core.default_agents_target(root, scope)
    block = core.agents_block(args.python or sys.executable, _cli_path())
    res = core.attach_agents(target, block, dry_run=args.dry_run)
    if res["action"] == "updated" and not res["changed"]:
        print(f"[已是最新] {res['path']}（块内容一致，无需改动）")
        return 0
    verb = {"created": "已创建并写入", "inserted": "已插入入口块到",
            "updated": "已更新入口块于"}[res["action"]]
    print(f"{verb} {res['path']}" + ("（dry-run，未落盘）" if args.dry_run else ""))
    scope_desc = ("自定义路径" if args.file
                  else "项目级（随项目走）" if scope == "project"
                  else "用户级（该用户所有会话生效）")
    print(f"  作用域：{scope_desc}")
    undo = "govhub.py detach"
    if args.file:
        undo += f" --file {args.file}"
    else:
        undo += " --scope " + scope
    print(f"  撤销：{undo}")
    if scope == "user":
        print("  提示：用户级入口对所有工作区生效——块内已写条件句，未启用 gov-hub 的项目自动忽略。")
    return 0


def cmd_detach(args: argparse.Namespace) -> int:
    """移除入口块。不加闸：撤销必须永远可用——用户拒绝（MUTED）或未声明时也要能撤销。"""
    root = Path(args.root or ".").resolve()
    target = Path(args.file) if args.file else core.default_agents_target(root, args.scope)
    res = core.detach_agents(target, dry_run=args.dry_run)
    msg = {"absent": f"[无文件] {res['path']}",
           "no-block": f"[无入口块] {res['path']}（未找到 gov-hub 标记，未改动）",
           "removed": f"已移除入口块：{res['path']}",
           "removed-and-deleted-file": f"已移除入口块，且文件只剩空内容 → 已删除 {res['path']}"}
    print(msg[res["action"]] + ("（dry-run，未落盘）" if args.dry_run else ""))
    return 0


def cmd_ensure(args: argparse.Namespace) -> int:
    """第 0 步：唯一的入口命令，把"是否要问用户"变成命令输出，不交给模型判断。

    已启用 → [OK] 继续干活；已拒绝 → [MUTED] 静默继续；
    未声明 → 打印欢迎说明 + [NEXT] 指令（含三岔口原文），模型下一步只需调用提问工具。
    """
    root = Path(args.root or ".").resolve()
    if core.declined(root):
        print("[MUTED] 本区已声明不启用项目地图；按项目原有方式继续，不要再提。")
        return 0
    if core.load_config(root) is not None:
        print("[OK] 本区已启用项目地图。动手前先 lookup，别蛮力翻目录。")
        return 0
    print(explain_text(root))
    print("[NEXT] 上面这段话请完整展示给用户，然后**立刻**调用 ask_user_question（正文里问不产生弹窗），"
          "选项如下：")
    print("  1. 启用（推荐） → 你运行：PYTHON CLI_PATH init --main <本工作区>，"
          "再把本轮已读过的权威文件用 add 逐条登记")
    print("  2. 暂不启用，别再问 → 你运行：PYTHON CLI_PATH init --decline")
    print("  3. 这次先不用 → 不写任何文件，继续回答")
    return 0


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
    p = sub.add_parser("suggest", help="从路线迹提炼登记提案（提案制，不改盘）")
    p.add_argument("--root", default=".")
    p.add_argument("--min", type=int, default=2, help="同一终点最少命中次数")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_suggest)
    p = sub.add_parser("add", help="登记一条资产（单命令，自动机检+同步索引）")
    p.add_argument("path", help="权威文件路径（相对主工作区根或绝对路径）")
    p.add_argument("--root", default=".")
    p.add_argument("--title", default="", help="条目标题（默认为文件名）")
    p.add_argument("--keywords", default="", help="逗号分隔；含用户本次的实际问法")
    p.add_argument("--answers", default="", help="这条能回答什么问题（一行）")
    p.add_argument("--id", default="", help="条目 id（默认按文件名自动生成）")
    p.add_argument("--type", default="asset", help="条目类型（默认 asset）")
    p.add_argument("--authority", default="canonical",
                   choices=["canonical", "derived", "generated"])
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser("ensure", help="第 0 步入口检查：已启用/已拒绝/未声明，未声明时直接给出提问指令")
    p.add_argument("--root", default=".")
    p.set_defaults(fn=cmd_ensure)
    p = sub.add_parser("attach", help="把入口块写进 AGENTS.md（标记块/幂等/可 detach 还原）")
    p.add_argument("--root", default=".")
    p.add_argument("--scope", default="project", choices=["project", "user"],
                   help="project=工作区 AGENTS.md；user=$DSH_HOME/AGENTS.md（全项目生效）")
    p.add_argument("--file", default="", help="显式指定目标文件（优先于 --scope）")
    p.add_argument("--python", default="", help="写进块里的 Python 解释器路径")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_attach)
    p = sub.add_parser("detach", help="从 AGENTS.md 移除入口块（块外内容不动）")
    p.add_argument("--root", default=".")
    p.add_argument("--scope", default="project", choices=["project", "user"])
    p.add_argument("--file", default="")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_detach)
    args = ap.parse_args()
    return args.fn(args)

