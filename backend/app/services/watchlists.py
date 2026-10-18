from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings

_lock = threading.Lock()


def _path() -> Path:
    root = Path(settings.data_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root / "watchlists.json"


def _load() -> dict[str, Any]:
    p = _path()
    if not p.exists():
        data = {
            "groups": [
                {
                    "id": "default",
                    "name": "自选股",
                    "created_at": time.time(),
                    "stocks": [],
                }
            ]
        }
        _save(data)
        return data
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict[str, Any]) -> None:
    p = _path()
    tmp = p.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(p)


def list_groups() -> list[dict[str, Any]]:
    with _lock:
        return list(_load().get("groups") or [])


def create_group(name: str) -> dict[str, Any]:
    name = (name or "").strip() or "未命名分组"
    with _lock:
        data = _load()
        group = {
            "id": uuid.uuid4().hex[:10],
            "name": name,
            "created_at": time.time(),
            "stocks": [],
        }
        data.setdefault("groups", []).append(group)
        _save(data)
        return group


def rename_group(group_id: str, name: str) -> dict[str, Any]:
    with _lock:
        data = _load()
        for g in data.get("groups") or []:
            if g["id"] == group_id:
                g["name"] = (name or "").strip() or g["name"]
                _save(data)
                return g
    raise KeyError(group_id)


def delete_group(group_id: str) -> None:
    with _lock:
        data = _load()
        groups = data.get("groups") or []
        if len(groups) <= 1:
            raise ValueError("至少保留一个分组")
        data["groups"] = [g for g in groups if g["id"] != group_id]
        if len(data["groups"]) == len(groups):
            raise KeyError(group_id)
        _save(data)


def add_stocks(group_id: str, items: list[dict[str, str]]) -> dict[str, Any]:
    with _lock:
        data = _load()
        for g in data.get("groups") or []:
            if g["id"] != group_id:
                continue
            seen = {s["code"] for s in g.get("stocks") or []}
            for it in items:
                code = str(it.get("code") or "").zfill(6)
                if not code.isdigit() or code in seen:
                    continue
                g.setdefault("stocks", []).append(
                    {
                        "code": code,
                        "name": str(it.get("name") or code),
                        "market": str(it.get("market") or ""),
                        "added_at": time.time(),
                    }
                )
                seen.add(code)
            _save(data)
            return g
    raise KeyError(group_id)


def remove_stock(group_id: str, code: str) -> dict[str, Any]:
    code = code.zfill(6)
    with _lock:
        data = _load()
        for g in data.get("groups") or []:
            if g["id"] != group_id:
                continue
            g["stocks"] = [s for s in (g.get("stocks") or []) if s.get("code") != code]
            _save(data)
            return g
    raise KeyError(group_id)


def get_group(group_id: str) -> dict[str, Any]:
    with _lock:
        for g in _load().get("groups") or []:
            if g["id"] == group_id:
                return g
    raise KeyError(group_id)
