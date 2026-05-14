"""
DeepSeek LLM 封装
- 统一调用接口（OpenAI 兼容协议）
- JSON 解析容错（处理 ```json 包裹等）
- 5 大场景 prompt
"""

import json
import os
import re
from typing import Any

import requests
import streamlit as st


def _get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except Exception:
        return os.environ.get(key, default)


def _api_key() -> str:
    return _get_secret("DEEPSEEK_API_KEY", "")


def _base_url() -> str:
    return _get_secret("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")


def call_llm(
    prompt: str,
    system: str | None = None,
    model: str = "deepseek-chat",
    json_mode: bool = False,
    temperature: float = 0.7,
    timeout: int = 60,
) -> str:
    """调用 DeepSeek，返回字符串内容。失败抛异常。"""
    key = _api_key()
    if not key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，请在 secrets.toml 或 设置 中填入")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    r = requests.post(
        f"{_base_url()}/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    if r.status_code != 200:
        raise RuntimeError(f"DeepSeek 调用失败: {r.status_code} {r.text[:200]}")
    j = r.json()
    return j["choices"][0]["message"]["content"]


def call_llm_json(prompt: str, system: str | None = None, **kwargs) -> Any:
    """调用并解析 JSON。"""
    content = call_llm(prompt, system=system, json_mode=True, **kwargs)
    return _parse_json_robust(content)


def _parse_json_robust(text: str) -> Any:
    """容错 JSON 解析：剥离 ```json 包裹、首尾杂文等"""
    text = text.strip()
    # 剥 markdown 包裹
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # 找第一个 { 或 [
    first_brace = min(
        (text.find(c) for c in "{[" if text.find(c) >= 0),
        default=-1,
    )
    if first_brace > 0:
        text = text[first_brace:]
    # 找最后一个 } 或 ]
    last_brace = max(text.rfind("}"), text.rfind("]"))
    if last_brace >= 0:
        text = text[: last_brace + 1]
    return json.loads(text)


# ============ 场景 1：随口说生成菜谱 ============
def generate_recipe(user_input: str) -> dict:
    system = "你是中餐家常菜专家，输出结构化菜谱。"
    prompt = f"""用户想做：{user_input}

请严格按以下 JSON 格式输出，不要任何其他文字：
{{
  "name": "菜名",
  "servings": 2,
  "cook_minutes": 数字(预估总耗时分钟),
  "tags": ["家常" 或 "快手" 或 "宴客" 或 "孩子" 或 "素菜" 等],
  "ingredients": [
    {{"name": "食材名", "quantity": 数字, "unit": "单位"}}
  ],
  "steps": [
    "步骤1详细描述(含火候/时间)",
    "步骤2..."
  ]
}}

要求：步骤详细，分量精确到家常单位（个/根/克/勺）。返回纯 JSON。"""
    return call_llm_json(prompt, system=system, temperature=0.6)


# ============ 场景 2：基于冰箱推荐今晚菜 ============
def recommend_dishes(inventory: list[dict], recipes: list[dict], n: int = 3) -> list[dict]:
    inv_text = "\n".join(
        f"- {i['name']} {i.get('quantity', '')}{i.get('unit', '')}（剩 {i.get('days_left', '?')} 天）"
        for i in inventory
    ) or "（冰箱是空的）"

    rec_text = "\n".join(
        f"- {r['name']}（{','.join(r.get('tags', []))}）食材: {','.join(ing['name'] for ing in r.get('ingredients', []))}"
        for r in recipes[:30]
    ) or "（暂无收藏菜谱）"

    system = "你是中餐家常菜专家，根据冰箱现有食材推荐菜。"
    prompt = f"""我的冰箱（含临期天数）：
{inv_text}

我已收藏的菜谱：
{rec_text}

请推荐 {n} 道今晚可做的菜，按以下规则：
1. 优先使用临期食材（剩余天数小的优先）
2. 优先匹配我已收藏的菜谱（source 标 "收藏"，否则标 "新建议"）
3. 食材尽量从冰箱里取

严格返回 JSON：
{{"dishes": [
  {{"name": "菜名", "reason": "为什么推荐(一句话)", "missing": ["缺少的食材1"], "source": "收藏" 或 "新建议"}}
]}}"""
    out = call_llm_json(prompt, system=system, temperature=0.7)
    if isinstance(out, dict):
        return out.get("dishes", [])
    return out if isinstance(out, list) else []


# ============ 场景 3：语音/小票批量入库（文本结构化） ============
def parse_purchase_text(text: str) -> list[dict]:
    """口语描述或小票OCR文本 -> 结构化食材列表"""
    system = "你帮我把超市购物描述结构化。"
    prompt = f"""用户描述了刚买的食材（可能来自语音转写或小票文字）：
\"\"\"{text}\"\"\"

请提取食材并返回 JSON：
{{"items": [
  {{"name": "食材名", "quantity": 数字, "unit": "单位(g/个/根/把/瓶等)", "category": "蔬菜/肉类/蛋奶/水产/水果/调料/主食/零食/其他", "estimated_shelf_days": 数字(预估保质期天数), "location": "冷藏/冷冻/常温"}}
]}}

换算规则：
- "一斤" = 500 克，"半斤" = 250 克，"两斤" = 1000 克
- "一把"、"一撮"、"一袋" 等保留原单位
- 忽略价格、日期、收银员、收据号
- 自动判断保质期与存放位置（叶菜≈3天冷藏，肉类≈2天冷藏或30天冷冻，根茎类≈14天常温/冷藏）
- 只输出能识别的食材，不要编造

返回纯 JSON。"""
    out = call_llm_json(prompt, system=system, temperature=0.3)
    if isinstance(out, dict):
        return out.get("items", [])
    return out if isinstance(out, list) else []


# ============ 场景 4：智能扣减库存 ============
def plan_deduction(recipe_ingredients: list[dict], inventory: list[dict]) -> list[dict]:
    """根据菜谱用量 + 库存现状，规划扣减方案。"""
    inv_text = "\n".join(
        f"- id={i['id']} 名称={i['name']} 数量={i.get('quantity')}{i.get('unit', '')}"
        for i in inventory
    )
    rec_text = "\n".join(
        f"- {ing['name']} {ing.get('quantity', '')}{ing.get('unit', '')}"
        for ing in recipe_ingredients
    )

    system = "你帮我把菜谱用量映射到库存条目的扣减计划。"
    prompt = f"""菜谱用量：
{rec_text}

当前库存：
{inv_text}

请输出扣减计划，把菜谱的每种食材映射到库存条目（同义词要识别，比如"小葱"=葱、"鸡蛋"=蛋）。
当单位不一致时智能换算：
- 一勺生抽 ≈ 15ml
- 一撮盐 ≈ 2g
- 葱花一撮 ≈ 5g（按葱根数算的话约 0.3 根）

严格返回 JSON：
{{"deductions": [
  {{"inventory_id": "库存条目id", "deduct_quantity": 数字, "reason": "(简短说明换算逻辑)"}}
]}}

如果某菜谱食材在库存里找不到，跳过即可。"""
    out = call_llm_json(prompt, system=system, temperature=0.2)
    if isinstance(out, dict):
        return out.get("deductions", [])
    return out if isinstance(out, list) else []


# ============ 场景 5：估算保质期（添加食材时辅助） ============
def estimate_shelf_days(name: str, location: str = "冷藏") -> int:
    try:
        prompt = f"食材「{name}」在「{location}」环境下的常见保质期是多少天？只回答一个整数，不要其他文字。"
        content = call_llm(prompt, temperature=0.1)
        m = re.search(r"\d+", content)
        if m:
            return int(m.group())
    except Exception:
        pass
    # 兜底默认
    defaults = {"冷冻": 30, "冷藏": 7, "常温": 14}
    return defaults.get(location, 7)
