"""购物清单页"""

from collections import defaultdict

import streamlit as st

from core import storage
from core.utils import LOCATIONS, INGREDIENT_CATEGORIES, add_days, fmt_qty, today_str


def render():
    mode = st.session_state.get("shop_mode", "list")
    if mode == "list":
        _render_list()
    elif mode == "finish":
        _render_finish()


def _render_shop_row(s: dict, strikethrough: bool) -> None:
    """渲染一行购物项，checkbox 状态与 is_checked 双向绑定（同一 key，靠状态对比触发保存）"""
    c1, c2, c3 = st.columns([1, 6, 1])
    key = f"shop_chk_{s['id']}"
    current = bool(s.get("is_checked", False))
    new_val = c1.checkbox(" ", key=key, value=current, label_visibility="collapsed")
    label = f"{s['name']} **{fmt_qty(s.get('quantity', ''))}{s.get('unit', '')}**"
    if strikethrough:
        label = f"~~{label}~~"
    c2.markdown(label)
    if c3.button("✕", key=f"shop_del_{s['id']}"):
        storage.delete_shopping_item(s["id"])
        st.rerun()
    if new_val != current:
        s["is_checked"] = new_val
        storage.update_shopping_item(s)
        st.rerun()


def _render_list():
    st.title("🛒 购物清单")

    items = storage.list_shopping()
    unchecked = [s for s in items if not s.get("is_checked")]
    checked = [s for s in items if s.get("is_checked")]

    # ========== 快捷添加 ==========
    with st.expander("➕ 记一笔（临时添加）", expanded=False):
        c1, c2, c3 = st.columns([3, 2, 1])
        name = c1.text_input("名称", key="quick_shop_name", label_visibility="collapsed", placeholder="名称")
        qty = c2.text_input("数量", key="quick_shop_qty", value="1", label_visibility="collapsed")
        unit = c3.text_input("单位", key="quick_shop_unit", value="个", label_visibility="collapsed")
        if st.button("加入", key="add_quick_shop", use_container_width=True):
            if name.strip():
                storage.add_shopping_items([{
                    "name": name.strip(),
                    "quantity": qty,
                    "unit": unit,
                    "source": "manual",
                }])
                st.rerun()

    # 常买快捷
    freq = storage.list_frequent_ingredients()
    if freq:
        with st.expander(f"⚡ 常买快捷（{len(freq)} 项）"):
            st.caption("点击直接加入清单（默认 1 份）")
            cols = st.columns(3)
            for i, f in enumerate(freq):
                with cols[i % 3]:
                    if st.button(
                        f"+ {f['name']}",
                        key=f"freq_{i}",
                        use_container_width=True,
                    ):
                        storage.add_shopping_items([{
                            "name": f["name"],
                            "quantity": 1,
                            "unit": f.get("default_unit", "个"),
                            "source": "frequent",
                        }])
                        st.rerun()

    # ========== 待买列表 ==========
    st.markdown(f"### 📝 待买（{len(unchecked)}）")
    if not unchecked:
        st.info("清单是空的，从菜谱或上方记一笔添加吧")
    else:
        # 按来源分组
        by_source = defaultdict(list)
        for s in unchecked:
            src = s.get("source", "manual")
            label = "📋 " + src.replace("recipe:", "") if src.startswith("recipe:") else "📝 其他"
            by_source[label].append(s)

        for src_label, group in by_source.items():
            st.markdown(f"**{src_label}**")
            for s in group:
                _render_shop_row(s, strikethrough=False)

    # ========== 已购列表 ==========
    if checked:
        st.markdown(f"### ✅ 已购（{len(checked)}）")
        for s in checked:
            _render_shop_row(s, strikethrough=True)

    # ========== 完成采购 ==========
    if checked:
        st.markdown("---")
        if st.button(
            f"🎒 采购完成 → 选择入库（{len(checked)} 项）",
            use_container_width=True,
            type="primary",
        ):
            st.session_state.shop_mode = "finish"
            st.rerun()


def _render_finish():
    if st.button("← 返回", key="back_finish"):
        st.session_state.shop_mode = "list"
        st.rerun()
    st.title("🎒 采购完成 → 入库")

    items = storage.list_shopping()
    checked = [s for s in items if s.get("is_checked")]
    if not checked:
        st.info("没有已勾选的项")
        return

    st.caption("勾选要入库的项，调整数量/单位/位置")
    to_stock = []
    for i, s in enumerate(checked):
        c1, c2 = st.columns([1, 9])
        in_stock = c1.checkbox("", value=True, key=f"in_{s['id']}")
        with c2:
            cc1, cc2, cc3 = st.columns([3, 2, 2])
            name = cc1.text_input("名称", value=s["name"], key=f"fin_name_{s['id']}", label_visibility="collapsed")
            try:
                qty_default = float(s.get("quantity", 1))
            except Exception:
                qty_default = 1.0
            qty = cc2.number_input(
                "数量",
                value=qty_default,
                min_value=0.0,
                key=f"fin_qty_{s['id']}",
                label_visibility="collapsed",
            )
            unit = cc3.text_input(
                "单位", value=s.get("unit", "个"), key=f"fin_unit_{s['id']}", label_visibility="collapsed"
            )
            cc4, cc5, cc6 = st.columns(3)
            loc = cc4.selectbox(
                "位置", LOCATIONS, index=0, key=f"fin_loc_{s['id']}", label_visibility="collapsed"
            )
            cat = cc5.selectbox(
                "分类",
                INGREDIENT_CATEGORIES,
                index=0,
                key=f"fin_cat_{s['id']}",
                label_visibility="collapsed",
            )
            shelf = cc6.number_input(
                "保质期天数",
                value=7,
                min_value=1,
                key=f"fin_shelf_{s['id']}",
                label_visibility="collapsed",
            )
        if in_stock and name.strip():
            to_stock.append({
                "name": name.strip(),
                "quantity": float(qty),
                "unit": unit,
                "location": loc,
                "category": cat,
                "shelf_days": int(shelf),
                "added_at": today_str(),
                "expire_at": add_days(today_str(), int(shelf)),
            })

    st.markdown("---")
    if st.button(
        f"✅ 入库 {len(to_stock)} 项，并清空已购",
        use_container_width=True,
        type="primary",
        disabled=not to_stock,
    ):
        for it in to_stock:
            storage.add_inventory_item(it)
        storage.clear_shopping_checked()
        st.success(f"已入库 {len(to_stock)} 项")
        st.session_state.shop_mode = "list"
        st.rerun()

    if st.button("仅清空已购（不入库）", use_container_width=True):
        storage.clear_shopping_checked()
        st.session_state.shop_mode = "list"
        st.rerun()
