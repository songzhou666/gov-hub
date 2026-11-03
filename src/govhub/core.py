# -*- coding: utf-8 -*-
"""gov-hub 通用层核心：scope 协议 / 登记表 / 四段健康灯。

设计约束（docs/DESIGN.md §0）：
- 范围永远是"声明的"：启发式只产候选，确认后才固化；
- 扫描产物一律携带 scope 指纹，失配即 stale；
- loose 档零假设：不解析命名、不要求结构。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as e:  # pragma: no cover
    raise SystemExit("[FATAL] 需要 PyYAML：pip install pyyaml") from e

CONFIG_NAME = "gov-hub.yaml"
DECLINE_NAME = "gov-hub.declined"
REGISTRY_NAME = "registry.yaml"
CONFIG_VERSION = 1

# init 探测的标记文件：存在即视为候选范围依据
MARKERS = [".git", "AGENTS.md", "CLAUDE.md", "package.json", "pyproject.toml",
           "go.mod", "Cargo.toml", CONFIG_NAME]

# 隐含排除：任何配置都生效，无需用户声明
BUILTIN_EXCLUDE = ["**/.git/**", "**/node_modules/**", "**/__pycache__/**"]


# ── 配置 ──────────────────────────────────────────────────────
def default_config() -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "scope": {"roots": ["."], "exclude": []},
        "layout": "loose",
        "containers": {},
        "window_days": 30,
        "thresholds": {"gap_yellow_max": 5},
    }


def load_config(root: Path) -> dict[str, Any] | None:
    """读取 gov-hub.yaml；不存在返回 None（不推断，交给 init 确认关）。"""
    path = root / CONFIG_NAME
    if not path.is_file():
        return None
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict) or int(cfg.get("version", 0)) != CONFIG_VERSION:
        raise SystemExit(f"[FATAL] {CONFIG_NAME} 缺失或 version != {CONFIG_VERSION}")
    # 冻结纪律：新字段带默认值，旧配置零改动可读
    merged = default_config()
    for k, v in cfg.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k].update(v)
        else:
            merged[k] = v
    return merged


def fingerprint(cfg: dict[str, Any], root: Path) -> str:
    """scope 指纹 = hash(roots + exclude + version)。产物失配即 stale。"""
    material = repr(sorted(cfg["scope"]["roots"]) + sorted(cfg["scope"]["exclude"])) \
        + f"|v{cfg['version']}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def config_path(root: Path) -> Path:
    return root / CONFIG_NAME


def declined(root: Path) -> bool:
    """用户已明确拒绝治理 → 静默模式，agent 不再询问。"""
    return (root / DECLINE_NAME).is_file()


# ── init：候选探测（只产候选，不落决定） ─────────────────────────
def detect_candidates(start: Path) -> list[dict[str, str]]:
    """向上扫描标记文件，返回候选范围清单（路径 + 依据）。"""
    candidates: dict[str, str] = {}
    cur = start.resolve()
    for _ in range(4):  # 最多向上 4 级，避免跑穿盘根
        hits = [m for m in MARKERS if (cur / m).exists()]
        if hits:
            candidates[str(cur)] = "标记: " + ", ".join(hits)
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return [{"path": p, "reason": r} for p, r in candidates.items()]


def write_config(root: Path, cfg: dict[str, Any]) -> Path:
    path = config_path(root)
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")
    return path


# ── 登记表 ────────────────────────────────────────────────────
def load_registry(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    """从第一个 scope root 读取登记表（约定放主根）。"""
    main = resolve_root(root, cfg["scope"]["roots"][0])
    path = main / REGISTRY_NAME
    if not path.is_file():
        raise SystemExit(f"[FATAL] 登记表不存在：{path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "entries" not in data:
        raise SystemExit(f"[FATAL] 登记表结构非法（缺 entries）：{path}")
    for e in data["entries"]:
        e.setdefault("keywords", [])
        e.setdefault("type", "asset")
        e.setdefault("authority", "canonical")
        e.setdefault("answers", "")
    return data


def resolve_root(root: Path, r: str) -> Path:
    p = Path(r)
    return p if p.is_absolute() else (root / p).resolve()


def iter_scoped_files(root: Path, cfg: dict[str, Any]):
    """遍历所有 scope roots 下的文件（应用排除 glob）。"""
    seen: set[str] = set()
    for r in cfg["scope"]["roots"]:
        base = resolve_root(root, r)
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            rel = os.path.relpath(dirpath, base).replace("\\", "/")
            dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__")]
            for fn in filenames:
                f = Path(dirpath) / fn
                s = str(f)
                if s in seen:
                    continue
                seen.add(s)
                relf = (rel + "/" + fn) if rel != "." else fn
                if any(Path(relf).match(pat.replace("**/", "*/")) for pat in cfg["scope"]["exclude"]):
                    continue
                yield f, relf


def check_registry(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    """机检①：登记表每条 path 在盘；返回 {ok, problems, stats}。"""
    reg = load_registry(root, cfg)
    problems: list[str] = []
    by_type: dict[str, int] = {}
    main = resolve_root(root, cfg["scope"]["roots"][0])
    for e in reg["entries"]:
        t = str(e.get("type", "asset"))
        by_type[t] = by_type.get(t, 0) + 1
        p = main / str(e.get("path", ""))
        if not (p.is_file() or p.is_dir()):
            problems.append(f"路径不在盘: {e.get('path')}（{e.get('id')}）")
    return {
        "ok": not problems,
        "problems": problems,
        "stats": {"total": len(reg["entries"]), "by_type": by_type,
                  "updated": str(reg.get("updated", "")), "version": reg.get("version")},
    }


# ── generated 产物：检索索引（携带指纹，失配即重建） ──────────────
INDEX_DIR = ".govhub"
AUTH_RANK = {"canonical": 0, "generated": 1, "derived": 2, "legacy": 3}
WEIGHTS = {"id": 5.0, "title": 4.0, "keywords": 4.0, "answers": 1.5, "path": 0.5}


def build_index(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    """从登记表重建 generated 检索索引。索引永不作为 canonical 引用。"""
    reg = load_registry(root, cfg)
    main = resolve_root(root, cfg["scope"]["roots"][0])
    idx_dir = main / INDEX_DIR
    idx_dir.mkdir(exist_ok=True)
    index = {
        "fingerprint": fingerprint(cfg, root),
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "registry_signature": registry_signature(reg),
        "entries": [{k: e.get(k, "") for k in
                     ("id", "type", "title", "path", "answers", "authority")}
                    | {"keywords": e.get("keywords", [])}
                    for e in reg["entries"]],
    }
    (idx_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def load_index(root: Path, cfg: dict[str, Any], *, allow_rebuild: bool = True) -> dict[str, Any]:
    """读索引；缺失或指纹失配即 stale → 重建（generated 产物可随时重建）。"""
    main = resolve_root(root, cfg["scope"]["roots"][0])
    path = main / INDEX_DIR / "index.json"
    fp = fingerprint(cfg, root)
    if path.is_file():
        try:
            index = json.loads(path.read_text(encoding="utf-8"))
            if index.get("fingerprint") == fp:
                return index
        except (json.JSONDecodeError, OSError):
            pass
    if not allow_rebuild:
        return {"stale": True, "fingerprint": fp, "entries": []}
    index = build_index(root, cfg)
    index["rebuilt"] = True
    return index


def registry_signature(reg: dict[str, Any]) -> str:
    """登记表内容签名：updated 字段会忘改，内容才是真相。"""
    material = sorted(f"{e.get('id')}|{e.get('path')}|{e.get('updated', '')}"
                      for e in reg.get("entries", []))
    return hashlib.sha256(repr(material).encode("utf-8")).hexdigest()[:12]


def registry_changed(root: Path, cfg: dict[str, Any], index: dict[str, Any]) -> bool:
    """登记表内容签名与索引记录不一致 → 需要重建（不信任 updated 字段）。"""
    return registry_signature(load_registry(root, cfg)) != index.get("registry_signature", "")


def record_trail(root: Path, cfg: dict[str, Any], terms: list[str],
                 top_hit: dict[str, Any]) -> None:
    """路线迹：lookup 命中即自动记录 起点(查询词)→终点(权威文件)。
    写 .govhub/trail.jsonl（generated，可删）；失败静默——迹是增益，不是依赖。"""
    try:
        main = resolve_root(root, cfg["scope"]["roots"][0])
        idx_dir = main / INDEX_DIR
        idx_dir.mkdir(exist_ok=True)
        dest = (f"{top_hit.get('id')}|{top_hit.get('path')}"
                if top_hit is not None else None)
        rec = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "terms": " ".join(terms),
               "dest": dest}
        with open(idx_dir / "trail.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def load_trail(root: Path, cfg: dict[str, Any]) -> list[dict[str, str]]:
    """读路线迹（generated，缺失返回空）。"""
    main = resolve_root(root, cfg["scope"]["roots"][0])
    path = main / INDEX_DIR / "trail.jsonl"
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def suggest_proposals(root: Path, cfg: dict[str, Any], min_hits: int = 2) -> list[dict[str, Any]]:
    """从路线迹提炼登记提案（只提案，不落盘——提案制）。

    规则：同一终点被 ≥min_hits 次查到 → 建议把用户实际的查法（terms）
    补进该条目的 keywords，或新建条目草稿。
    """
    reg = load_registry(root, cfg)
    known = {str(e.get("id")): e for e in reg["entries"]}
    routes: dict[str, dict[str, set[str]]] = {}
    for t in load_trail(root, cfg):
        dest = str(t.get("dest", ""))
        if "|" not in dest:
            continue
        eid, path = dest.split("|", 1)
        routes.setdefault(eid, {"path": path, "terms": set(), "hits": 0})
        routes[eid]["terms"].add(str(t.get("terms", "")).strip())
        routes[eid]["hits"] += 1
    # 整句问法不适合当关键词：提案只用短词，且过滤疑问句式（整句仅作覆盖缺口依据）
    _Q = ("吗", "呢", "几份", "几个", "什么", "哪", "怎么", "多少", "如何",
          "是否", "有没有", "在哪", "发现了")
    def _short(ts: set[str]) -> list[str]:
        return sorted(t for t in ts
                      if 0 < len(t) <= 14 and not any(q in t for q in _Q))
    proposals = []
    for eid, r in sorted(routes.items(), key=lambda kv: -len(kv[1]["terms"])):
        if r["hits"] < min_hits:
            continue
        terms = _short(r["terms"])
        if not terms:
            continue
        e = known.get(eid)
        if e is not None:
            new_kw = [t for t in terms if t not in [str(k) for k in e.get("keywords", [])]]
            if not new_kw:
                continue
            proposals.append({"kind": "补充关键词", "id": eid, "path": r["path"],
                              "suggest_keywords": new_kw, "hits": r["hits"],
                              "yaml": f"  keywords: {list(e.get('keywords', [])) + new_kw}"})
        else:
            proposals.append({"kind": "新建条目草稿", "id": eid, "path": r["path"],
                              "suggest_keywords": terms, "hits": r["hits"],
                              "yaml": (f"- id: {eid.split('.')[0]}.draft\n"
                                       f"  type: asset\n  title: （待填）\n  path: {r['path']}\n"
                                       f"  keywords: {terms}\n  answers: （待填）\n"
                                       f"  authority: canonical")})
    # 覆盖缺口：同主题被问 ≥min_hits 次但从未命中——用户在找地图上没有的东西
    misses: dict[str, dict[str, object]] = {}
    for t in load_trail(root, cfg):
        if t.get("dest"):
            continue
        terms_str = str(t.get("terms", "")).strip()
        if not terms_str:
            continue
        m = misses.setdefault(terms_str, {"terms": terms_str, "hits": 0})
        m["hits"] = int(m["hits"]) + 1  # type: ignore[assignment]
    for m in misses.values():
        if int(m["hits"]) >= min_hits:  # type: ignore[arg-type]
            proposals.append({"kind": "覆盖缺口（多次问但地图没有）",
                              "id": None, "path": None,
                              "suggest_keywords": [str(m["terms"])],
                              "hits": m["hits"],
                              "yaml": (f"# 用户 {m['hits']} 次查「{m['terms']}」均未命中——"
                                       f"找到对应权威文件后用 add 登记；keywords 用短主题词"
                                       f"（去掉疑问句式），answers 写清能回答什么")})
    return proposals


def search(index: dict[str, Any], terms: list[str], limit: int = 12) -> list[dict[str, Any]]:
    """关键词 → 资产单元：分层打分（相等满分、包含半分），权威级并列排序。"""
    toks = [t.strip().lower() for t in terms if t.strip()]
    if not toks:
        return []
    scored = []
    for e in index.get("entries", []):
        total = 0.0
        for field, weight in WEIGHTS.items():
            vals = e.get(field)
            vals = [str(v).lower() for v in vals] if isinstance(vals, list) \
                else [str(vals or "").lower()]
            for tok in toks:
                for v in vals:
                    if not v:
                        continue
                    if v == tok:
                        total += weight
                    elif tok in v:
                        total += weight / 2
                    elif v in tok:
                        # 反方向包含：agent 常把整句问法丢进来（如"登录验证码那里发现了什么问题"），
                        # 此时登记关键词 ⊂ 查询词，也应命中（给半分，精确匹配仍优先）
                        total += weight / 2
        if total > 0:
            scored.append((total, AUTH_RANK.get(str(e.get("authority")), 9), e))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [{**e, "score": round(s, 1)} for s, _, e in scored[:limit]]


# ── 四段健康灯 ────────────────────────────────────────────────
def lamps(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    reg_check = check_registry(root, cfg)
    containers = cfg.get("containers") or {}
    mapped = cfg.get("layout") in ("mapped", "convention") and bool(containers)
    recent_cut = datetime.now() - timedelta(days=int(cfg.get("window_days", 30)))
    activity: dict[str, int] = {}
    gaps: list[dict] = []
    if mapped:
        reg = load_registry(root, cfg)
        tokens: set[str] = set()
        for e in reg["entries"]:
            for kw in e.get("keywords", []):
                if len(str(kw)) >= 2:
                    tokens.add(str(kw).lower())
            if len(str(e.get("title", ""))) >= 2:
                tokens.add(str(e.get("title", "")).lower())
        covered = {str(e.get("path", "")).replace("\\", "/").lower() for e in reg["entries"]}
        for c in containers:
            base = resolve_root(root, c)
            if not base.is_dir():
                continue
            for d in base.iterdir():
                if not d.is_dir():
                    continue
                mtime = datetime.fromtimestamp(d.stat().st_mtime)
                if mtime < recent_cut:
                    continue
                activity[c] = activity.get(c, 0) + 1
                rel = f"{c}/{d.name}".lower()
                theme = d.name.split("_", 1)[1] if "_" in d.name else d.name
                hit_path = any(rel.startswith(p) or p.startswith(rel) for p in covered)
                hit_token = any(k in theme.lower() or theme.lower() in k
                                for k in tokens if len(k) >= 2)
                if not hit_path and not hit_token:
                    gaps.append({"dir": rel, "mtime": mtime.strftime("%Y-%m-%d")})

    n_gaps = len(gaps)
    yellow_max = int(cfg.get("thresholds", {}).get("gap_yellow_max", 5))
    total_recent = sum(activity.values())
    return {
        "check": reg_check,
        "fingerprint": fingerprint(cfg, root),
        "lamps": {
            "supply": {"level": "green" if reg_check["ok"] else "red",
                       "detail": f"登记表一致性 {'通过' if reg_check['ok'] else 'FAIL'}"
                                 f"（{reg_check['stats']['total']} 条）"},
            "execute": {"level": "green" if mapped and total_recent else "yellow",
                        "detail": (f"近 {cfg['window_days']} 天产出 {total_recent} 个目录"
                                   if mapped else "loose 档不追踪执行活跃度（升 mapped 档启用）")},
            "output": {"level": "green" if mapped and total_recent else "yellow",
                       "detail": "；".join(f"{k}: {v}" for k, v in activity.items())
                                 if mapped else "未启用（需 mapped 档声明 containers）"},
            "backfill": {"level": ("green" if n_gaps == 0 else
                                   "yellow" if n_gaps <= yellow_max else "red")
                         if mapped else "yellow",
                         "detail": (f"回灌缺口 {n_gaps} 个" if mapped
                                    else "未启用（需 mapped 档声明 containers）")},
        },
        "gaps": gaps,
    }



# ── AGENTS.md 入口注册（attach / detach）────────────────────────
# 设计约束：
# - 只动自己的标记块：<!-- gov-hub:begin --> … <!-- gov-hub:end -->，块外一个字节不改；
# - 幂等：重复 attach 只替换块内容，不重复追加；
# - 可精确还原：detach 后文件应与 attach 前逐字节一致（无块时删除我们创建的文件）；
# - 插在 H1 之后/文件顶部：DSH 预算超限截的是尾部，块必须靠前才不会被截掉。
AGENTS_BEGIN = "<!-- gov-hub:begin managed block; 用 govhub.py attach/detach 维护，请勿手改块内 -->"
AGENTS_END = "<!-- gov-hub:end -->"

AGENTS_BLOCK_TMPL = """{begin}
## 查找项目内容：先查项目地图（gov-hub）

**若当前工作区根存在 `gov-hub.yaml`**，凡遇到"某内容在哪个文件 / 什么时候做过什么 /
有哪些记录 / 之前测试结论在哪"这类问题：

- 先运行 `{python} "{cli}" lookup "<关键词或整句问法>" --root <当前工作区>`，
  按返回的权威文件作答，**不要递归扫描目录**（尤其 node_modules）；
- 未命中 → 按原有方式查找；找到权威文件后立即登记（地图靠这一步生长）：
  `{python} "{cli}" add <文件相对路径> --keywords <用户问法,主题词> --answers "<能回答什么>"`；
- 项目地图只索引工作区文件，**不含对话内容**；问"上次会话聊了什么"不要翻会话日志。

**若不存在 `gov-hub.yaml`**：**先把用户的问题正常答完，不要阻塞**；回答完之后在同一个回复
末尾一次性邀请——运行 `{python} "{cli}" init --explain --root <当前工作区>` 并展示说明，
问一次是否启用（同意则 `init --main <工作区>`，并把本轮实际用到的权威文件用 `add` 登记）。
用户拒绝后永久静默，不得再提。

变更/撤销：`govhub.py attach` / `govhub.py detach`（整块可删，不影响其他内容）。
{end}"""


def agents_block(python_exe: str, cli_path: str) -> str:
    return AGENTS_BLOCK_TMPL.format(begin=AGENTS_BEGIN, end=AGENTS_END,
                                    python=python_exe or "python",
                                    cli=cli_path)


def _strip_block(text: str) -> tuple[str, bool]:
    """移除标记块并归一化拼接处空行，返回 (其余内容, 是否找到块)。"""
    start = text.find(AGENTS_BEGIN)
    if start < 0:
        return text, False
    end = text.find(AGENTS_END, start)
    if end < 0:
        return text, False
    end += len(AGENTS_END)
    before = text[:start].rstrip("\n")
    after = text[end:].lstrip("\n")
    if before and after:
        return before + "\n\n" + after, True
    if before:
        return before + "\n", True
    return after, True


def attach_agents(path: Path, block: str, dry_run: bool = False) -> dict[str, Any]:
    """写入/更新入口块。返回 {action, path, created_file}。"""
    existed = path.is_file()
    original = path.read_text(encoding="utf-8") if existed else ""
    stripped, had_block = _strip_block(original)
    if had_block:  # 原位替换：块留在原位置（通常是 H1 之后），周围字节不动
        start = original.find(AGENTS_BEGIN)
        end = original.find(AGENTS_END, start) + len(AGENTS_END)
        tail = original[end:]
        new = original[:start] + block + (tail if tail.startswith("\n") else "\n" + tail.lstrip("\n"))
        action = "updated"
    elif existed:
        lines = stripped.splitlines(keepends=True)
        idx = next((i for i, ln in enumerate(lines) if re.match(r"^#\s+\S", ln)), None)
        if idx is None:
            new = block + "\n\n" + stripped.lstrip("\n")
        else:
            head = "".join(lines[:idx + 1]).rstrip("\n")
            tail = "".join(lines[idx + 1:]).lstrip("\n")
            new = head + "\n\n" + block + "\n"
            if tail:
                new += "\n" + tail
        action = "inserted"
    else:
        new = block + "\n"
        action = "created"
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new, encoding="utf-8")
    return {"action": action, "path": str(path), "created_file": not existed,
            "changed": new != original}


def detach_agents(path: Path, dry_run: bool = False) -> dict[str, Any]:
    """移除入口块；块外内容原样保留；若移除后只剩空白则删除文件。"""
    if not path.is_file():
        return {"action": "absent", "path": str(path)}
    original = path.read_text(encoding="utf-8")
    stripped, had = _strip_block(original)
    if not had:
        return {"action": "no-block", "path": str(path)}
    new = stripped.strip("\n")
    new = new + "\n" if new else ""
    if not dry_run:
        if new.strip():
            path.write_text(new, encoding="utf-8")
            return {"action": "removed", "path": str(path)}
        path.unlink()
        return {"action": "removed-and-deleted-file", "path": str(path)}
    return {"action": "removed", "path": str(path)}


def default_agents_target(root: Path, scope: str) -> Path:
    """scope=project → <工作区>/AGENTS.md；scope=user → $DSH_HOME/AGENTS.md 或 ~/.dsh/AGENTS.md。"""
    if scope == "project":
        return root / "AGENTS.md"
    home = os.environ.get("DSH_HOME") or str(Path.home() / ".dsh")
    return Path(home) / "AGENTS.md"
