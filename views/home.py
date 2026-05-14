"""首页 Dashboard"""

import streamlit as st

from core import llm, storage
from core.utils import days_left, fmt_qty, today_str


def _go(page: str):
    st.session_state.nav = page
    st.rerun()


def render():
    st.title("🍳 Cook")
    st.caption("Joseph，今天想吃啥？")

    inventory = storage.list_inventory()
    recipes = storage.list_recipes()
    shopping = storage.list_shopping()
    pending_tasks = storage.list_tasks(status="pending")

    # ====== 临期食材卡片 ======
    expiring = []
    for it in inventory:
        dl = days_left(it.get("expire_at"))
        if dl is not None and dl <= 3:
            expiring.append({**it, "days_left": dl})

    if expiring:
        st.markdown('<div class="cook-card cook-card-warn">', unsafe_allow_html=True)
        st.markdown("**⏰ 临期食材** · 优先吃掉")
        for it in expiring[:5]:
            dl = it["days_left"]
            badge = (
                f'<span class="cook-danger">已过期 {-dl} 天</span>'
                if dl < 0
                else f'<span class="cook-danger">还剩 {dl} 天</span>'
                if dl <= 1
                else f'<span class="cook-warn">{dl} 天</span>'
            )
            st.markdown(
                f"- {it['name']} {fmt_qty(it.get('quantity'))}{it.get('unit', '')} · {badge}",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    # ====== AI 推荐今晚菜 ======
    st.markdown('<div class="cook-card cook-card-info">', unsafe_allow_html=True)
    st.markdown("**🤖 AI 推荐今晚菜**")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption("基于冰箱现有食材 + 你的收藏")
    with col2:
        if st.button("生成", key="ai_recommend", use_container_width=True):
            with st.spinner("AI 思考中..."):
                try:
                    inv_with_days = []
                    for i in inventory:
                        dl = days_left(i.get("expire_at"))
                        inv_with_days.append({**i, "days_left": dl if dl is not None else "?"})
                    dishes = llm.recommend_dishes(inv_with_days, recipes, n=3)
                    st.session_state.recommended_dishes = dishes
                except Exception as e:
                    st.error(f"调用失败：{e}")

    dishes = st.session_state.get("recommended_dishes", [])
    if dishes:
        for d in dishes:
            tag = "🌟" if d.get("source") == "收藏" else "✨"
            st.markdown(f"**{tag} {d.get('name', '?')}**")
            st.caption(d.get("reason", ""))
            missing = d.get("missing", [])
            if missing:
                st.caption(f"⚠️ 缺：{', '.join(missing)}")
    st.markdown("</div>", unsafe_allow_html=True)

    # ====== 待办做菜 ======
    if pending_tasks:
        st.markdown('<div class="cook-card cook-card-ok">', unsafe_allow_html=True)
        st.markdown(f"**📝 待办做菜（{len(pending_tasks)}）**")
        for t in pending_tasks[:3]:
            st.markdown(f"- {t.get('recipe_name')} · {t.get('planned_date')}")
        if st.button("查看全部 →", key="goto_tasks", use_container_width=True):
            _go("菜谱")
        st.markdown("</div>", unsafe_allow_html=True)

    # ====== 购物清单 ======
    unchecked_shop = [s for s in shopping if not s.get("is_checked")]
    if unchecked_shop:
        st.markdown('<div class="cook-card">', unsafe_allow_html=True)
        st.markdown(f"**🛒 待买（{len(unchecked_shop)}）**")
        for s in unchecked_shop[:5]:
            st.markdown(f"- {s.get('name')} {fmt_qty(s.get('quantity', ''))}{s.get('unit', '')}")
        if st.button("去购物清单 →", key="goto_shop", use_container_width=True):
            _go("购物")
        st.markdown("</div>", unsafe_allow_html=True)

    # ====== 数据概览 ======
    c1, c2, c3 = st.columns(3)
    c1.metric("菜谱", len(recipes))
    c2.metric("冰箱", len(inventory))
    c3.metric("待办", len(pending_tasks))

    # ====== 随口说生成菜谱 ======
    st.markdown("---")
    st.markdown("**💬 随口说一句，AI 给你菜谱**")
    user_input = st.text_input(
        "比如：我想吃番茄牛腩、川味回锅肉、清蒸鲈鱼",
        key="quick_recipe_input",
        label_visibility="collapsed",
        placeholder="比如：番茄牛腩",
    )
    if st.button("✨ 生成菜谱", key="quick_gen", use_container_width=True, type="primary"):
        if not user_input.strip():
            st.warning("说点什么吧")
        else:
            with st.spinner("AI 写菜谱中..."):
                try:
                    recipe = llm.generate_recipe(user_input.strip())
                    st.session_state.generated_recipe = recipe
                except Exception as e:
                    st.error(f"生成失败：{e}")

    gen = st.session_state.get("generated_recipe")
    if gen:
        with st.expander(f"📖 {gen.get('name', '新菜谱')}", expanded=True):
            st.caption(
                f"⏱️ {gen.get('cook_minutes', '?')} 分钟 · {gen.get('servings', 2)} 人份 · "
                + " ".join(f"`{t}`" for t in gen.get("tags", []))
            )
            st.markdown("**🥬 食材**")
            for ing in gen.get("ingredients", []):
                st.markdown(
                    f"- {ing.get('name')} {fmt_qty(ing.get('quantity', ''))}{ing.get('unit', '')}"
                )
            st.markdown("**👨‍🍳 步骤**")
            for i, step in enumerate(gen.get("steps", []), 1):
                st.markdown(f"{i}. {step}")

            c1, c2 = st.columns(2)
            if c1.button("💾 保存到菜谱", key="save_gen", use_container_width=True):
                gen.setdefault("tags", [])
                storage.upsert_recipe(gen)
                st.success("已保存")
                del st.session_state.generated_recipe
                st.rerun()
            if c2.button("🗑️ 丢弃", key="discard_gen", use_container_width=True):
                del st.session_state.generated_recipe
                st.rerun()
