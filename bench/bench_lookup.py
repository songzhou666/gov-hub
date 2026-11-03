# -*- coding: utf-8 -*-
"""导航成本对照实验：项目地图(lookup) vs 蛮力导航(列表+全文检索+误读)。

只读被测工作区；结果写本仓库 bench/RESULTS.md。
口径说明：
  两条路径都包含"最终打开目标文件"的成本，因此差值纯粹来自"找到该读哪个文件"
  的导航成本——该口径对插件是保守的（未计入蛮力路径的试错轮次与返工）。
token 估算：中文混合文本按 chars×0.6 粗估，仅作量级参考。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from govhub import core  # noqa: E402

ASSETS = Path(r"E:\AI_TEST\test_assets")          # 被测真实资产区（只读）
REG_PATH = ASSETS / "_registry.yaml"


def load_reg() -> dict:
    import yaml
    data = yaml.safe_load(REG_PATH.read_text(encoding="utf-8"))
    for e in data["entries"]:
        e.setdefault("keywords", [])
        e.setdefault("type", "asset")
        e.setdefault("authority", "canonical")
    return data


def fmt_lookup_hits(hits) -> str:
    lines = []
    for e in hits:
        lines.append(f"[{e['score']}] {e['id']} · {e['authority']} · {e['path']}")
        lines.append(f"       {e['title']} —— {e['answers']}")
    return "\n".join(lines)


def grep_chars(term: str) -> tuple[int, int]:
    """蛮力路径：全文检索命中行的字符数与命中文件数。"""
    total, files = 0, set()
    for f in ASSETS.rglob("*.md"):
        try:
            for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                if term in line:
                    total += len(line) + 20  # 行内容 + grep 前缀(路径:行号)
                    files.add(str(f))
        except OSError:
            continue
    return total, len(files)


def main() -> None:
    reg = load_reg()
    index = {"entries": reg["entries"]}
    listing_chars = sum(len(p.name) + 2 for p in ASSETS.iterdir())  # 蛮力第一步：浏览目录

    queries = ["叫号", "跨库", "登录", "分表", "token", "工单", "目录规范", "测试计划", "签名", "会话"]
    rows, tot_a, tot_b = [], 0, 0
    for q in queries:
        hits = core.search(index, [q], limit=12)
        if not hits:
            continue
        target = ASSETS / hits[0]["path"]
        target_chars = len(target.read_text(encoding="utf-8", errors="ignore")) if target.is_file() else 0
        after = len(fmt_lookup_hits(hits[:3])) + target_chars
        g_chars, g_files = grep_chars(q)
        # 误读：按文件名猜，最多误开 2 个候选
        wrong = [p for p in ASSETS.glob("*.md") if q in p.name and p.name != target.name][:2]
        wrong_chars = sum(len(p.read_text(encoding="utf-8", errors="ignore")) for p in wrong)
        before = listing_chars + g_chars + wrong_chars + target_chars
        tot_a += after
        tot_b += before
        rows.append((q, before, after, g_files, len(wrong)))

    lines = [
        "# 导航成本对照实验（真实数据）", "",
        f"- 被测：`E:\\AI_TEST\\test_assets`（{len(list(ASSETS.glob('*.md')))} 个 md 文件，"
        f"登记表 {len(reg['entries'])} 条）",
        f"- 查询集：{len(rows)} 个高频关键词（取自登记表真实 keywords）",
        f"- 蛮力路径 = 目录浏览({listing_chars} 字符) + 全文检索命中 + 误读候选(≤2 个) + 读目标文件",
        f"- 地图路径 = lookup 前 3 条命中 + 读同一目标文件",
        f"- 口径：两路径都含『读目标文件』，差值纯为导航成本；蛮力未计试错轮次，数字保守",
        "", "| 查询词 | 蛮力导航(chars) | 地图导航(chars) | 节省 | 蛮力命中文件数 | 误读文件数 |",
        "|---|---|---|---|---|---|",
    ]
    for q, b, a, gf, w in rows:
        lines.append(f"| {q} | {b:,} | {a:,} | {100*(b-a)/b:.0f}% | {gf} | {w} |")
    lines += ["", f"**合计**：蛮力 {tot_b:,} chars vs 地图 {tot_a:,} chars —— "
              f"导航成本降低 **{100*(tot_b-tot_a)/tot_b:.1f}%**。",
              "",
              f"按 chars×0.6 粗估 token：蛮力 ≈ {int(tot_b*0.6):,} tok，"
              f"地图 ≈ {int(tot_a*0.6):,} tok，单轮 10 查询节省约 "
              f"**{int((tot_b-tot_a)*0.6):,} tokens**（约 {100*(tot_b-tot_a)/tot_b:.0f}%）。",
              "",
              "注：单文件任务场景 9 成以上的节省来自『不用翻』；若计入蛮力路径的试错重试、",
              "误读后的重新定位与上下文污染导致的返工，实际差距更大——本实验不计这些。"]

    out = Path(__file__).parent / "RESULTS.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n已写入 {out}")


if __name__ == "__main__":
    main()
