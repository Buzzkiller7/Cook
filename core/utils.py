"""通用工具函数"""

from datetime import date, datetime, timedelta


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date() if "T" in s else date.fromisoformat(s)
    except Exception:
        return None


def days_left(expire_at: str | None) -> int | None:
    d = parse_date(expire_at)
    if not d:
        return None
    return (d - date.today()).days


def add_days(d: date | str, n: int) -> str:
    if isinstance(d, str):
        d = parse_date(d) or date.today()
    return (d + timedelta(days=n)).isoformat()


def today_str() -> str:
    return date.today().isoformat()


def fmt_qty(q) -> str:
    """数量格式化：去掉无意义的小数"""
    try:
        f = float(q)
        if f == int(f):
            return str(int(f))
        return f"{f:.1f}"
    except Exception:
        return str(q)


# 用于库存与购物的食材分类常量
INGREDIENT_CATEGORIES = ["蔬菜", "肉类", "水产", "蛋奶", "水果", "主食", "调料", "零食", "其他"]
LOCATIONS = ["冷藏", "冷冻", "常温", "调料"]
RECIPE_TAGS = ["家常", "快手", "宴客", "孩子", "素菜", "汤", "凉菜", "主食", "早餐"]
