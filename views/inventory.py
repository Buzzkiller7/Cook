"""冰箱页：库存列表 + 添加 + AI 入库"""

import streamlit as st

from core import llm, storage
from core.utils import (
    INGREDIENT_CATEGORIES,
    LOCATIONS,
    add_days,
    days_left,
    fmt_qty,
    today_str,
)


def render():
    mode = st.session_state.get("inv_mode", "list")
    if mode == "list":
        _render_list()
    elif mode == "add_manual":
        _render_add_manual()
    elif mode == "add_ai":
        _render_add_ai()
    elif mode == "edit":
        _render_edit()


def _render_list():
    st.title("🧊 冰箱")

    c1, c2, c3 = st.columns(3)
    if c1.button("➕ 手动添加", use_container_width=True):
        st.session_state.inv_mode = "add_manual"
        st.rerun()
    if c2.button("🤖 AI 录入", use_container_width=True, type="primary"):
        st.session_state.inv_mode = "add_ai"
        st.rerun()
    if c3.button("🔄 刷新", use_container_width=True):
        storage.load_data(force_remote=True)
        st.rerun()

    loc = st.radio(
        "分区",
        ["全部"] + LOCATIONS,
        horizontal=True,
        key="inv_loc_filter",
        label_visibility="collapsed",
    )

    items = storage.list_inventory(location=loc)
    if not items:
        st.info("这里空空如也 🌫️")
        return

    # 临期分组
    expired, expiring, normal = [], [], []
    for it in items:
        dl = days_left(it.get("expire_at"))
        if dl is None:
            normal.append((it, dl))
        elif dl < 0:
            expired.append((it, dl))
        elif dl <= 3:
            expiring.append((it, dl))
        else:
            normal.append((it, dl))

    def _show(it, dl):
        with st.container():
            st.markdown('<div class="cook-card">', unsafe_allow_html=True)
            c1, c2 = st.columns([4, 1])
            with c1:
                badge = ""
                if dl is not None:
                    if dl < 0:
                        badge = f' <span class="cook-danger">⚠️ 已过期 {-dl} 天</span>'
                    elif dl <= 1:
                        badge = f' <span class="cook-danger">🔴 还剩 {dl} 天</span>'
                    elif dl <= 3:
                        badge = f' <span class="cook-warn">🟡 {dl} 天</span>'
                    else:
                        badge = f' <span class="cook-muted">🟢 {dl} 天</span>'
                st.markdown(
                    f"**{it['name']}** {fmt_qty(it.get('quantity', 0))}{it.get('unit', '')}{badge}",
                    unsafe_allow_html=True,
                )
                st.caption(f"{it.get('location', '?')} · 入库 {it.get('added_at', '?')}")
            with c2:
                if st.button("编辑", key=f"edit_inv_{it['id']}", use_container_width=True):
                    st.session_state.inv_mode = "edit"
                    st.session_state.edit_inv = dict(it)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    if expired:
        st.markdown("### ⚠️ 已过期")
        for it, dl in expired:
            _show(it, dl)
    if expiring:
        st.markdown("### ⏰ 临期（3 天内）")
        for it, dl in expiring:
            _show(it, dl)
    if normal:
        st.markdown("### ✅ 正常")
        for it, dl in normal:
            _show(it, dl)


def _render_add_manual():
    if st.button("← 返回", key="back_manual"):
        st.session_state.inv_mode = "list"
        st.rerun()
    st.title("➕ 手动添加食材")

    name = st.text_input("名称")
    c1, c2 = st.columns(2)
    qty = c1.number_input("数量", min_value=0.0, value=1.0, step=1.0)
    unit = c2.text_input("单位", value="个")
    location = st.selectbox("位置", LOCATIONS, index=0)
    category = st.selectbox("分类", INGREDIENT_CATEGORIES, index=0)
    shelf_days = st.number_input("保质期天数", min_value=1, value=7)

    if st.button("🤖 让 AI 帮我估保质期", use_container_width=True):
        if not name:
            st.warning("先填食材名")
        else:
            with st.spinner("..."):
                try:
                    shelf_days = llm.estimate_shelf_days(name, location)
                    st.session_state[f"ai_shelf_{name}"] = shelf_days
                    st.success(f"建议保质期 {shelf_days} 天，请手动调整或直接保存")
                except Exception as e:
                    st.warning(f"AI 不可用：{e}")

    if st.button("💾 保存", type="primary", use_container_width=True):
        if not name.strip():
            st.error("请填写名称")
        else:
            storage.add_inventory_item({
                "name": name.strip(),
                "quantity": float(qty),
                "unit": unit,
                "location": location,
                "category": category,
                "added_at": today_str(),
                "shelf_days": int(shelf_days),
                "expire_at": add_days(today_str(), int(shelf_days)),
            })
            st.success("已加入")
            st.session_state.inv_mode = "list"
            st.rerun()


def _render_add_ai():
    if st.button("← 返回", key="back_ai"):
        st.session_state.inv_mode = "list"
        st.rerun()
    st.title("🤖 AI 批量录入")
    st.caption("把刚买的东西用一句话告诉我，或粘贴小票文字")

    text = st.text_area(
        "描述",
        placeholder="例如：今天买了两斤排骨、五个西红柿、一把香菜、一瓶生抽",
        height=120,
        key="ai_input_text",
    )

    st.markdown("💡 提示：手机浏览器键盘上的「🎙️ 语音输入」直接用就行")

    if st.button("🔍 AI 解析", type="primary", use_container_width=True):
        if not text.strip():
            st.warning("先输入点东西")
        else:
            with st.spinner("AI 解析中..."):
                try:
                    items = llm.parse_purchase_text(text.strip())
                    st.session_state.ai_parsed_items = items
                except Exception as e:
                    st.error(f"解析失败：{e}")

    items = st.session_state.get("ai_parsed_items", [])
    if items:
        st.markdown(f"**解析出 {len(items)} 项，确认后入库：**")
        for i, it in enumerate(items):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            it["name"] = c1.text_input(
                "名称", value=it.get("name", ""), key=f"ai_name_{i}", label_visibility="collapsed"
            )
            it["quantity"] = c2.number_input(
                "数量",
                value=float(it.get("quantity") or 1),
                key=f"ai_qty_{i}",
                label_visibility="collapsed",
            )
            it["unit"] = c3.text_input(
                "单位", value=it.get("unit", "个"), key=f"ai_unit_{i}", label_visibility="collapsed"
            )
            if c4.button("✕", key=f"ai_del_{i}"):
                items.pop(i)
                st.session_state.ai_parsed_items = items
                st.rerun()
            c5, c6 = st.columns(2)
            it["location"] = c5.selectbox(
                "位置",
                LOCATIONS,
                index=LOCATIONS.index(it.get("location", "冷藏"))
                if it.get("location") in LOCATIONS
                else 0,
                key=f"ai_loc_{i}",
                label_visibility="collapsed",
            )
            shelf = it.get("estimated_shelf_days") or 7
            it["shelf_days"] = c6.number_input(
                "保质期天数",
                value=int(shelf),
                min_value=1,
                key=f"ai_shelf_{i}",
                label_visibility="collapsed",
            )

        st.session_state.ai_parsed_items = items

        if st.button("💾 全部入库", type="primary", use_container_width=True):
            for it in items:
                if not it.get("name", "").strip():
                    continue
                storage.add_inventory_item({
                    "name": it["name"].strip(),
                    "quantity": float(it.get("quantity", 1)),
                    "unit": it.get("unit", "个"),
                    "location": it.get("location", "冷藏"),
                    "category": it.get("category", "其他"),
                    "added_at": today_str(),
                    "shelf_days": int(it.get("shelf_days", 7)),
                    "expire_at": add_days(today_str(), int(it.get("shelf_days", 7))),
                })
            st.success(f"已入库 {len(items)} 项")
            st.session_state.pop("ai_parsed_items", None)
            st.session_state.inv_mode = "list"
            st.rerun()


def _render_edit():
    item = st.session_state.get("edit_inv", {})
    if st.button("← 返回", key="back_edit_inv"):
        st.session_state.inv_mode = "list"
        st.rerun()
    st.title(f"编辑：{item.get('name')}")

    item["name"] = st.text_input("名称", value=item.get("name", ""))
    c1, c2 = st.columns(2)
    item["quantity"] = c1.number_input("数量", value=float(item.get("quantity", 0)), min_value=0.0)
    item["unit"] = c2.text_input("单位", value=item.get("unit", ""))
    item["location"] = st.selectbox(
        "位置",
        LOCATIONS,
        index=LOCATIONS.index(item["location"]) if item.get("location") in LOCATIONS else 0,
    )
    item["category"] = st.selectbox(
        "分类",
        INGREDIENT_CATEGORIES,
        index=INGREDIENT_CATEGORIES.index(item["category"])
        if item.get("category") in INGREDIENT_CATEGORIES
        else 0,
    )
    item["expire_at"] = st.text_input("到期日 (YYYY-MM-DD)", value=item.get("expire_at", ""))

    c1, c2 = st.columns(2)
    if c1.button("💾 保存", type="primary", use_container_width=True):
        storage.update_inventory_item(item)
        st.session_state.inv_mode = "list"
        st.rerun()
    if c2.button("🗑️ 删除", use_container_width=True):
        storage.delete_inventory_item(item["id"])
        st.session_state.inv_mode = "list"
        st.rerun()
