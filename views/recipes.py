"""菜谱页：列表 / 详情 / 编辑 / 做菜模式"""

import time

import streamlit as st

from core import llm, storage
from core.utils import RECIPE_TAGS, fmt_qty, today_str


def render():
    mode = st.session_state.get("recipe_mode", "list")
    if mode == "list":
        _render_list()
    elif mode == "detail":
        _render_detail()
    elif mode == "edit":
        _render_edit()
    elif mode == "cooking":
        _render_cooking()
    elif mode == "tasks":
        _render_tasks()


# ============ 列表 ============
def _render_list():
    st.title("📖 菜谱")

    c1, c2 = st.columns([3, 1])
    if c1.button("📋 做菜待办", key="goto_tasks", use_container_width=True):
        st.session_state.recipe_mode = "tasks"
        st.rerun()
    if c2.button("➕ 新增", key="new_recipe", use_container_width=True, type="primary"):
        st.session_state.recipe_mode = "edit"
        st.session_state.edit_recipe = {"name": "", "tags": [], "ingredients": [], "steps": [], "servings": 2}
        st.rerun()

    kw = st.text_input("🔍 搜索菜名", key="recipe_search", label_visibility="collapsed", placeholder="搜索菜名")

    all_tags = ["全部"] + RECIPE_TAGS
    selected_tag = st.radio("标签", all_tags, horizontal=True, key="tag_filter", label_visibility="collapsed")

    recipes = storage.list_recipes(tag=selected_tag, keyword=kw)
    if not recipes:
        st.info("暂无菜谱，点 ➕ 新增 或回首页 AI 生成")
        return

    for r in recipes:
        with st.container():
            st.markdown('<div class="cook-card">', unsafe_allow_html=True)
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"**{r.get('name', '?')}**")
                tags = r.get("tags", [])
                if tags:
                    st.markdown(
                        " ".join(f'<span class="cook-tag">{t}</span>' for t in tags),
                        unsafe_allow_html=True,
                    )
                meta = []
                if r.get("cook_minutes"):
                    meta.append(f"⏱️{r['cook_minutes']}分")
                if r.get("servings"):
                    meta.append(f"{r['servings']}人份")
                if r.get("last_cooked_at"):
                    meta.append(f"上次:{r['last_cooked_at']}")
                if meta:
                    st.caption(" · ".join(meta))
            with c2:
                if st.button("查看", key=f"view_{r['id']}", use_container_width=True):
                    st.session_state.recipe_mode = "detail"
                    st.session_state.current_recipe_id = r["id"]
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)


# ============ 详情 ============
def _render_detail():
    rid = st.session_state.get("current_recipe_id")
    r = storage.get_recipe(rid)
    if not r:
        st.error("菜谱不存在")
        if st.button("← 返回"):
            st.session_state.recipe_mode = "list"
            st.rerun()
        return

    if st.button("← 返回列表", key="back_to_list"):
        st.session_state.recipe_mode = "list"
        st.rerun()

    st.title(r.get("name", ""))
    tags = r.get("tags", [])
    if tags:
        st.markdown(" ".join(f'<span class="cook-tag">{t}</span>' for t in tags), unsafe_allow_html=True)
    st.caption(f"⏱️ {r.get('cook_minutes', '?')} 分钟 · {r.get('servings', 2)} 人份")

    # 份数缩放
    factor = st.slider(
        "调整份数",
        min_value=1,
        max_value=10,
        value=int(r.get("servings", 2)),
        key="serving_slider",
    )
    scale = factor / max(1, int(r.get("servings", 2)))

    # 食材
    st.subheader("🥬 食材")
    inventory = {i["name"]: i for i in storage.list_inventory()}
    missing = []
    for ing in r.get("ingredients", []):
        name = ing.get("name", "")
        qty = ing.get("quantity", 0)
        try:
            qty_scaled = float(qty) * scale
        except Exception:
            qty_scaled = qty
        unit = ing.get("unit", "")
        in_fridge = name in inventory
        prefix = "✅" if in_fridge else "❌"
        if not in_fridge:
            missing.append({"name": name, "quantity": qty_scaled, "unit": unit})
        fridge_text = (
            f" · 冰箱有 {fmt_qty(inventory[name].get('quantity'))}{inventory[name].get('unit', '')}"
            if in_fridge
            else ""
        )
        st.markdown(f"{prefix} {name} **{fmt_qty(qty_scaled)}{unit}**{fridge_text}")

    # 步骤
    st.subheader("👨‍🍳 步骤")
    for i, step in enumerate(r.get("steps", []), 1):
        st.markdown(f"**{i}.** {step}")

    # 操作按钮
    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("🛒 加入购物清单", use_container_width=True):
        items = []
        for ing in r.get("ingredients", []):
            try:
                qty = float(ing.get("quantity", 0)) * scale
            except Exception:
                qty = ing.get("quantity", 0)
            items.append({
                "name": ing.get("name"),
                "quantity": qty,
                "unit": ing.get("unit", ""),
                "source": f"recipe:{r['name']}",
            })
        storage.add_shopping_items(items)
        st.success(f"已加入 {len(items)} 项")
    if c2.button("📝 加入做菜待办", use_container_width=True):
        storage.add_task({
            "recipe_id": r["id"],
            "recipe_name": r["name"],
            "servings": factor,
        })
        st.success("已加入待办")

    c3, c4 = st.columns(2)
    if c3.button("🔥 立即做菜", use_container_width=True, type="primary"):
        st.session_state.recipe_mode = "cooking"
        st.session_state.cooking_step = 0
        st.session_state.cooking_servings = factor
        st.rerun()
    if c4.button("✏️ 编辑", use_container_width=True):
        st.session_state.recipe_mode = "edit"
        st.session_state.edit_recipe = dict(r)
        st.rerun()

    st.markdown("---")
    with st.expander("🗑️ 删除菜谱"):
        if st.button("确认删除（不可恢复）", key="del_recipe", type="secondary"):
            storage.delete_recipe(r["id"])
            st.session_state.recipe_mode = "list"
            st.rerun()


# ============ 编辑 ============
def _render_edit():
    r = st.session_state.get("edit_recipe", {})
    is_new = not r.get("id")

    if st.button("← 取消", key="cancel_edit"):
        st.session_state.recipe_mode = "list" if is_new else "detail"
        st.rerun()

    st.title("✏️ 新建菜谱" if is_new else "编辑菜谱")

    r["name"] = st.text_input("菜名", value=r.get("name", ""))
    c1, c2 = st.columns(2)
    r["servings"] = c1.number_input("人份", value=int(r.get("servings", 2)), min_value=1, max_value=20)
    r["cook_minutes"] = c2.number_input("耗时(分钟)", value=int(r.get("cook_minutes", 15)), min_value=1, max_value=300)

    r["tags"] = st.multiselect("标签", RECIPE_TAGS, default=r.get("tags", []))

    # 食材
    st.subheader("🥬 食材")
    ings = r.get("ingredients", [])

    # 显示已有
    for i, ing in enumerate(ings):
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        ing["name"] = c1.text_input("名称", value=ing.get("name", ""), key=f"ing_name_{i}", label_visibility="collapsed")
        ing["quantity"] = c2.text_input("量", value=str(ing.get("quantity", "")), key=f"ing_qty_{i}", label_visibility="collapsed")
        ing["unit"] = c3.text_input("单位", value=ing.get("unit", ""), key=f"ing_unit_{i}", label_visibility="collapsed")
        if c4.button("✕", key=f"del_ing_{i}"):
            ings.pop(i)
            r["ingredients"] = ings
            st.session_state.edit_recipe = r
            st.rerun()
    if st.button("➕ 加一条食材", use_container_width=True):
        ings.append({"name": "", "quantity": "", "unit": ""})
        r["ingredients"] = ings
        st.session_state.edit_recipe = r
        st.rerun()

    # 步骤
    st.subheader("👨‍🍳 步骤")
    steps = r.get("steps", [])
    for i, s in enumerate(steps):
        c1, c2 = st.columns([10, 1])
        steps[i] = c1.text_area(
            f"步骤 {i+1}", value=s, key=f"step_{i}", height=70, label_visibility="collapsed"
        )
        if c2.button("✕", key=f"del_step_{i}"):
            steps.pop(i)
            r["steps"] = steps
            st.session_state.edit_recipe = r
            st.rerun()
    if st.button("➕ 加一步", use_container_width=True, key="add_step"):
        steps.append("")
        r["steps"] = steps
        st.session_state.edit_recipe = r
        st.rerun()

    r["steps"] = [s for s in steps if s.strip()]
    r["ingredients"] = [i for i in ings if i.get("name", "").strip()]

    st.markdown("---")
    if st.button("💾 保存", type="primary", use_container_width=True):
        if not r["name"].strip():
            st.error("请填写菜名")
        else:
            storage.upsert_recipe(r)
            st.success("已保存")
            st.session_state.recipe_mode = "list"
            if "edit_recipe" in st.session_state:
                del st.session_state.edit_recipe
            st.rerun()


# ============ 做菜模式 ============
def _render_cooking():
    rid = st.session_state.get("current_recipe_id")
    r = storage.get_recipe(rid)
    if not r:
        st.error("菜谱不存在")
        return

    steps = r.get("steps", [])
    cur = st.session_state.get("cooking_step", 0)
    servings = st.session_state.get("cooking_servings", r.get("servings", 2))
    scale = servings / max(1, int(r.get("servings", 2)))

    # 锁屏防关：让 Streamlit 一直保持活跃（用 toast 提示用户保持屏幕亮）
    st.markdown(
        f"<h1 style='font-size:28px;'>🔥 {r.get('name')}</h1>",
        unsafe_allow_html=True,
    )
    progress = (cur + 1) / max(1, len(steps))
    st.progress(progress, text=f"第 {cur + 1} / {len(steps)} 步")

    if cur < len(steps):
        st.markdown(
            f"<div class='cook-card' style='font-size:20px;line-height:1.8;'>"
            f"<b>步骤 {cur + 1}</b><br/>{steps[cur]}"
            f"</div>",
            unsafe_allow_html=True,
        )

        # 当前需要食材
        with st.expander("🥬 用到的食材"):
            for ing in r.get("ingredients", []):
                try:
                    qty = float(ing.get("quantity", 0)) * scale
                except Exception:
                    qty = ing.get("quantity", 0)
                st.markdown(f"- {ing.get('name')} **{fmt_qty(qty)}{ing.get('unit', '')}**")

        c1, c2, c3 = st.columns([1, 1, 2])
        if c1.button("← 上一步", use_container_width=True, disabled=cur == 0):
            st.session_state.cooking_step = max(0, cur - 1)
            st.rerun()
        if c2.button("下一步 →", use_container_width=True, type="primary", disabled=cur >= len(steps) - 1):
            st.session_state.cooking_step = cur + 1
            st.rerun()
        if cur == len(steps) - 1:
            if c3.button("✅ 完成做菜", use_container_width=True, type="primary"):
                _finish_cooking(r, scale)
        else:
            c3.button("✅ 完成做菜", use_container_width=True, disabled=True)
    else:
        st.success("步骤已结束，点完成扣减库存")
        if st.button("✅ 完成做菜", use_container_width=True, type="primary"):
            _finish_cooking(r, scale)

    if st.button("← 退出做菜（不扣库存）", use_container_width=True):
        st.session_state.recipe_mode = "detail"
        st.rerun()


def _finish_cooking(recipe, scale):
    # 准备扣减方案
    inventory = storage.list_inventory()
    scaled_ings = []
    for ing in recipe.get("ingredients", []):
        try:
            qty = float(ing.get("quantity", 0)) * scale
        except Exception:
            qty = ing.get("quantity", 0)
        scaled_ings.append({**ing, "quantity": qty})

    # 先尝试直接 name+unit 匹配扣
    deductions_simple = []
    for ing in scaled_ings:
        for x in inventory:
            if x["name"] == ing["name"] and x.get("unit") == ing.get("unit"):
                deductions_simple.append({
                    "name": x["name"],
                    "quantity": ing.get("quantity", 0),
                    "unit": x.get("unit", ""),
                })
                break

    st.session_state.cooking_deductions = deductions_simple
    st.session_state.cooking_recipe = recipe
    st.session_state.recipe_mode = "deduct_confirm"
    # 把菜谱的 last_cooked_at 更新
    recipe["last_cooked_at"] = today_str()
    storage.upsert_recipe(recipe)
    st.rerun()


# ============ 任务列表 ============
def _render_tasks():
    if st.button("← 返回菜谱", key="back_from_tasks"):
        st.session_state.recipe_mode = "list"
        st.rerun()

    st.title("📝 做菜待办")
    tasks = storage.list_tasks(status="pending")
    if not tasks:
        st.info("没有待办，去菜谱里加几个吧")
        return

    for t in tasks:
        with st.container():
            st.markdown('<div class="cook-card">', unsafe_allow_html=True)
            st.markdown(f"**{t.get('recipe_name')}**")
            st.caption(f"📅 {t.get('planned_date')} · {t.get('servings', 2)} 人份")
            c1, c2, c3 = st.columns(3)
            if c1.button("🔥 立即做", key=f"do_{t['id']}", use_container_width=True):
                st.session_state.current_recipe_id = t["recipe_id"]
                st.session_state.cooking_step = 0
                st.session_state.cooking_servings = t.get("servings", 2)
                st.session_state.recipe_mode = "cooking"
                # 完成做菜时也把任务标记完成
                st.session_state.cooking_task_id = t["id"]
                st.rerun()
            if c2.button("⏭️ 跳过", key=f"skip_{t['id']}", use_container_width=True):
                t["status"] = "skipped"
                storage.update_task(t)
                st.rerun()
            if c3.button("🗑️ 删除", key=f"del_task_{t['id']}", use_container_width=True):
                storage.delete_task(t["id"])
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)


# 把扣减确认页放在 recipes 模块里，复用 mode 机制（main 里只识别 list/detail/edit/cooking/tasks）
# 这里特殊处理，通过另外一个分支
def _render_deduct_confirm():
    deductions = st.session_state.get("cooking_deductions", [])
    recipe = st.session_state.get("cooking_recipe", {})

    st.title("✅ 完成做菜 - 确认扣减库存")
    st.caption(f"菜谱：{recipe.get('name', '')}")

    if not deductions:
        st.info("没有匹配到库存条目，是否使用 AI 智能识别（如葱花/盐等模糊单位）？")
    else:
        st.markdown("**将扣减以下库存：**")
        new_dedu = []
        for i, d in enumerate(deductions):
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.markdown(d["name"])
            qty = c2.number_input(
                "数量",
                value=float(d.get("quantity", 0) or 0),
                key=f"dedu_qty_{i}",
                label_visibility="collapsed",
            )
            unit = c3.markdown(d.get("unit", ""))
            new_dedu.append({**d, "quantity": qty})
        deductions = new_dedu

    if st.button("🤖 AI 智能扣减（推荐处理模糊用量）", use_container_width=True):
        with st.spinner("AI 处理中..."):
            try:
                inv = storage.list_inventory()
                plan = llm.plan_deduction(recipe.get("ingredients", []), inv)
                # 把 plan 转成 name/qty/unit 格式
                ai_dedu = []
                inv_by_id = {i["id"]: i for i in inv}
                for p in plan:
                    item = inv_by_id.get(p.get("inventory_id"))
                    if item:
                        ai_dedu.append({
                            "name": item["name"],
                            "quantity": p.get("deduct_quantity", 0),
                            "unit": item.get("unit", ""),
                        })
                st.session_state.cooking_deductions = ai_dedu
                st.rerun()
            except Exception as e:
                st.error(f"AI 调用失败：{e}")

    c1, c2 = st.columns(2)
    if c1.button("✅ 确认扣减并完成", use_container_width=True, type="primary"):
        storage.deduct_inventory(deductions)
        # 标记 task 完成
        tid = st.session_state.get("cooking_task_id")
        if tid:
            for t in storage.list_tasks():
                if t["id"] == tid:
                    t["status"] = "done"
                    t["completed_at"] = today_str()
                    storage.update_task(t)
                    break
            del st.session_state.cooking_task_id
        st.success("已完成并扣减库存！")
        st.session_state.recipe_mode = "list"
        for k in ["cooking_deductions", "cooking_recipe", "cooking_step", "cooking_servings"]:
            st.session_state.pop(k, None)
        time.sleep(0.5)
        st.rerun()
    if c2.button("跳过扣减", use_container_width=True):
        # 只标记完成，不扣
        tid = st.session_state.get("cooking_task_id")
        if tid:
            for t in storage.list_tasks():
                if t["id"] == tid:
                    t["status"] = "done"
                    t["completed_at"] = today_str()
                    storage.update_task(t)
                    break
            st.session_state.pop("cooking_task_id", None)
        st.session_state.recipe_mode = "list"
        for k in ["cooking_deductions", "cooking_recipe", "cooking_step", "cooking_servings"]:
            st.session_state.pop(k, None)
        st.rerun()


# 在 render() 里追加分支
_original_render = render


def render():
    mode = st.session_state.get("recipe_mode", "list")
    if mode == "deduct_confirm":
        _render_deduct_confirm()
        return
    _original_render()
