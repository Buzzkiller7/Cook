"""
存储层：本地 JSON + GitHub Gist 多设备同步
设计原则：
- 单一数据文件 cook_data.json（包含所有模块）
- 本地缓存优先，启动时尝试拉 Gist，关闭/修改时推 Gist
- Gist 不可用时降级到纯本地
"""

import json
import os
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests
import streamlit as st

# ============ 配置 ============
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DATA_FILE = DATA_DIR / "cook_data.json"

GIST_FILENAME = "cook_data.json"

# ============ 默认数据 ============
DEFAULT_DATA = {
    "version": 1,
    "recipes": [],
    "inventory": [],
    "shopping": [],
    "tasks": [],
    "frequent_ingredients": [
        {"name": "鸡蛋", "default_unit": "个", "category": "蛋奶"},
        {"name": "葱", "default_unit": "根", "category": "蔬菜"},
        {"name": "姜", "default_unit": "块", "category": "蔬菜"},
        {"name": "蒜", "default_unit": "瓣", "category": "蔬菜"},
        {"name": "盐", "default_unit": "g", "category": "调料"},
        {"name": "生抽", "default_unit": "ml", "category": "调料"},
        {"name": "食用油", "default_unit": "ml", "category": "调料"},
        {"name": "牛奶", "default_unit": "ml", "category": "蛋奶"},
        {"name": "西红柿", "default_unit": "个", "category": "蔬菜"},
        {"name": "土豆", "default_unit": "个", "category": "蔬菜"},
    ],
    "meta": {
        "last_synced_at": None,
    },
}


# ============ 本地读写 ============
def _read_local() -> dict:
    if not DATA_FILE.exists():
        _write_local(DEFAULT_DATA)
        return json.loads(json.dumps(DEFAULT_DATA))
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 补全缺失字段
        for k, v in DEFAULT_DATA.items():
            data.setdefault(k, v if not isinstance(v, (list, dict)) else json.loads(json.dumps(v)))
        return data
    except Exception as e:
        st.warning(f"本地数据读取失败，使用默认: {e}")
        return json.loads(json.dumps(DEFAULT_DATA))


def _write_local(data: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============ Gist 同步 ============
def _get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except Exception:
        return os.environ.get(key, default)


def _gist_enabled() -> bool:
    return bool(_get_secret("GITHUB_TOKEN")) and bool(_get_secret("GIST_ID"))


def _gist_pull() -> dict | None:
    """从 Gist 拉取数据。失败返回 None。"""
    if not _gist_enabled():
        return None
    token = _get_secret("GITHUB_TOKEN")
    gist_id = _get_secret("GIST_ID")
    try:
        r = requests.get(
            f"https://api.github.com/gists/{gist_id}",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        files = r.json().get("files", {})
        if GIST_FILENAME not in files:
            return None
        content = files[GIST_FILENAME].get("content", "")
        if not content:
            return None
        return json.loads(content)
    except Exception as e:
        st.warning(f"Gist 拉取失败（已降级本地）: {e}")
        return None


def _gist_push(data: dict) -> bool:
    if not _gist_enabled():
        return False
    token = _get_secret("GITHUB_TOKEN")
    gist_id = _get_secret("GIST_ID")
    try:
        payload = {
            "files": {
                GIST_FILENAME: {"content": json.dumps(data, ensure_ascii=False, indent=2)}
            }
        }
        r = requests.patch(
            f"https://api.github.com/gists/{gist_id}",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
            json=payload,
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        st.warning(f"Gist 推送失败（仅本地保存）: {e}")
        return False


# ============ 主 API（其他模块用这些） ============
def load_data(force_remote: bool = False) -> dict:
    """加载数据。优先 session_state 缓存，其次 Gist，最后本地。"""
    if "data" in st.session_state and not force_remote:
        return st.session_state.data

    # 启动时优先拉 Gist
    remote = _gist_pull()
    if remote is not None:
        # 合并缺失字段
        for k, v in DEFAULT_DATA.items():
            remote.setdefault(k, v if not isinstance(v, (list, dict)) else json.loads(json.dumps(v)))
        _write_local(remote)
        st.session_state.data = remote
        return remote

    local = _read_local()
    st.session_state.data = local
    return local


def save_data(data: dict | None = None, push_remote: bool = True) -> None:
    """保存数据。同步本地 + Gist。"""
    if data is None:
        data = st.session_state.get("data", DEFAULT_DATA)
    data["meta"]["last_synced_at"] = datetime.now().isoformat()
    _write_local(data)
    st.session_state.data = data
    if push_remote:
        _gist_push(data)


def reset_data() -> None:
    fresh = json.loads(json.dumps(DEFAULT_DATA))
    save_data(fresh)


def export_json() -> str:
    return json.dumps(load_data(), ensure_ascii=False, indent=2)


def import_json(content: str) -> tuple[bool, str]:
    try:
        data = json.loads(content)
        if not isinstance(data, dict):
            return False, "JSON 根节点必须是对象"
        # 补全字段
        for k, v in DEFAULT_DATA.items():
            data.setdefault(k, v if not isinstance(v, (list, dict)) else json.loads(json.dumps(v)))
        save_data(data)
        return True, "导入成功"
    except Exception as e:
        return False, f"导入失败：{e}"


# ============ 小工具：生成 ID ============
def new_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000)}"


# ============ 业务便捷方法 ============
# Recipes
def list_recipes(tag: str | None = None, keyword: str | None = None) -> list[dict]:
    data = load_data()
    recipes = data.get("recipes", [])
    if tag and tag != "全部":
        recipes = [r for r in recipes if tag in r.get("tags", [])]
    if keyword:
        kw = keyword.strip().lower()
        recipes = [r for r in recipes if kw in r.get("name", "").lower()]
    return sorted(recipes, key=lambda r: r.get("last_cooked_at") or "", reverse=True)


def get_recipe(rid: str) -> dict | None:
    for r in load_data().get("recipes", []):
        if r["id"] == rid:
            return r
    return None


def upsert_recipe(recipe: dict) -> None:
    data = load_data()
    if not recipe.get("id"):
        recipe["id"] = new_id("rec")
        recipe["created_at"] = date.today().isoformat()
    found = False
    for i, r in enumerate(data["recipes"]):
        if r["id"] == recipe["id"]:
            data["recipes"][i] = recipe
            found = True
            break
    if not found:
        data["recipes"].append(recipe)
    save_data(data)


def delete_recipe(rid: str) -> None:
    data = load_data()
    data["recipes"] = [r for r in data["recipes"] if r["id"] != rid]
    save_data(data)


# Inventory
def list_inventory(location: str | None = None) -> list[dict]:
    data = load_data()
    items = data.get("inventory", [])
    if location and location != "全部":
        items = [i for i in items if i.get("location") == location]
    # 临期排序
    def sort_key(i):
        return i.get("expire_at") or "9999-12-31"
    return sorted(items, key=sort_key)


def add_inventory_item(item: dict) -> None:
    data = load_data()
    item.setdefault("id", new_id("inv"))
    item.setdefault("added_at", date.today().isoformat())
    data["inventory"].append(item)
    save_data(data)


def update_inventory_item(item: dict) -> None:
    data = load_data()
    for i, x in enumerate(data["inventory"]):
        if x["id"] == item["id"]:
            data["inventory"][i] = item
            break
    save_data(data)


def delete_inventory_item(iid: str) -> None:
    data = load_data()
    data["inventory"] = [x for x in data["inventory"] if x["id"] != iid]
    save_data(data)


def deduct_inventory(deductions: list[dict]) -> None:
    """扣减库存。deductions: [{name, quantity, unit}]"""
    data = load_data()
    for d in deductions:
        for x in data["inventory"]:
            if x["name"] == d["name"] and x.get("unit") == d.get("unit"):
                x["quantity"] = max(0, float(x.get("quantity", 0)) - float(d.get("quantity", 0)))
                break
    # 数量为 0 的自动清理（可选）
    data["inventory"] = [x for x in data["inventory"] if float(x.get("quantity", 0)) > 0]
    save_data(data)


# Shopping
def list_shopping() -> list[dict]:
    return load_data().get("shopping", [])


def add_shopping_items(items: list[dict]) -> None:
    data = load_data()
    for it in items:
        it.setdefault("id", new_id("shop"))
        it.setdefault("is_checked", False)
        it.setdefault("created_at", date.today().isoformat())
        data["shopping"].append(it)
    save_data(data)


def update_shopping_item(item: dict) -> None:
    data = load_data()
    for i, x in enumerate(data["shopping"]):
        if x["id"] == item["id"]:
            data["shopping"][i] = item
            break
    save_data(data)


def delete_shopping_item(sid: str) -> None:
    data = load_data()
    data["shopping"] = [x for x in data["shopping"] if x["id"] != sid]
    save_data(data)


def clear_shopping_checked() -> None:
    data = load_data()
    data["shopping"] = [x for x in data["shopping"] if not x.get("is_checked")]
    save_data(data)


# Tasks (做菜待办)
def list_tasks(status: str | None = None) -> list[dict]:
    data = load_data()
    tasks = data.get("tasks", [])
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    return sorted(tasks, key=lambda t: t.get("planned_date") or "")


def add_task(task: dict) -> None:
    data = load_data()
    task.setdefault("id", new_id("task"))
    task.setdefault("status", "pending")
    task.setdefault("planned_date", date.today().isoformat())
    data["tasks"].append(task)
    save_data(data)


def update_task(task: dict) -> None:
    data = load_data()
    for i, x in enumerate(data["tasks"]):
        if x["id"] == task["id"]:
            data["tasks"][i] = task
            break
    save_data(data)


def delete_task(tid: str) -> None:
    data = load_data()
    data["tasks"] = [x for x in data["tasks"] if x["id"] != tid]
    save_data(data)


# Frequent ingredients
def list_frequent_ingredients() -> list[dict]:
    return load_data().get("frequent_ingredients", [])


def add_frequent_ingredient(ing: dict) -> None:
    data = load_data()
    data["frequent_ingredients"].append(ing)
    save_data(data)


def delete_frequent_ingredient(name: str) -> None:
    data = load_data()
    data["frequent_ingredients"] = [
        x for x in data["frequent_ingredients"] if x.get("name") != name
    ]
    save_data(data)
