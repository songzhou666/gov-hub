# -*- coding: utf-8 -*-
"""gov-hub 通用层核心：scope 协议 / 登记表 / 四段健康灯。

设计约束（docs/DESIGN.md §0）：
- 范围永远是"声明的"：启发式只产候选，确认后才固化；
- 扫描产物一律携带 scope 指纹，失配即 stale；
- loose 档零假设：不解析命名、不要求结构。
"""
from __future__ import annotations

import hashlib
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
        if not p.is_file():
            problems.append(f"路径不在盘: {e.get('path')}（{e.get('id')}）")
    return {
        "ok": not problems,
        "problems": problems,
        "stats": {"total": len(reg["entries"]), "by_type": by_type,
                  "updated": str(reg.get("updated", "")), "version": reg.get("version")},
    }


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
