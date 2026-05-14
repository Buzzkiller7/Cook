"""我的：备份/恢复 / 常买快捷库 / 状态"""

import os

import streamlit as st

from core import storage
from core.utils import INGREDIENT_CATEGORIES, today_str


def _get_secret(key, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return os.environ.get(key, default)


def render():
    st.title("⚙️ 我的")

    # ====== 同步状态 ======
    st.markdown("### ☁️ 数据同步状态")
    gist_enabled = bool(_get_secret("GITHUB_TOKEN")) and bool(_get_secret("GIST_ID"))
    if gist_enabled:
        st.success(f"已启用 GitHub Gist 同步 · 最后同步：{storage.load_data().get('meta', {}).get('last_synced_at', '?')}")
    else:
        st.info("未配置 Gist 同步，数据仅存本地。可在 Streamlit 控制台的 Secrets 中配置 `GITHUB_TOKEN` 和 `GIST_ID`")

    if st.button("🔄 强制重新同步", use_container_width=True):
        with st.spinner("..."):
            storage.load_data(force_remote=True)
            st.success("已同步")
            st.rerun()

    # ====== 备份与恢复 ======
    st.markdown("### 💾 备份与恢复")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "📥 导出全部数据 (JSON)",
            data=storage.export_json(),
            file_name=f"cook_backup_{today_str()}.json",
            mime="application/json",
            use_container_width=True,
        )
    with c2:
        uploaded = st.file_uploader("📤 导入 JSON", type=["json"], label_visibility="collapsed")
        if uploaded is not None:
            content = uploaded.read().decode("utf-8")
            ok, msg = storage.import_json(content)
            (st.success if ok else st.error)(msg)
            if ok:
                st.rerun()

    # ====== 常买食材快捷库 ======
    st.markdown("### ⚡ 常买食材快捷库")
    freq = storage.list_frequent_ingredients()
    for i, f in enumerate(freq):
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        c1.markdown(f["name"])
        c2.markdown(f.get("default_unit", ""))
        c3.markdown(f.get("category", ""))
        if c4.button("✕", key=f"del_freq_{i}"):
            storage.delete_frequent_ingredient(f["name"])
            st.rerun()

    with st.expander("➕ 添加常买"):
        c1, c2, c3 = st.columns([3, 2, 2])
        n = c1.text_input("名称", key="freq_new_name")
        u = c2.text_input("单位", key="freq_new_unit", value="个")
        cat = c3.selectbox("分类", INGREDIENT_CATEGORIES, key="freq_new_cat")
        if st.button("加入", use_container_width=True, key="add_freq_btn"):
            if n.strip():
                storage.add_frequent_ingredient({
                    "name": n.strip(),
                    "default_unit": u,
                    "category": cat,
                })
                st.rerun()

    # ====== 危险区 ======
    st.markdown("### ⚠️ 危险区")
    with st.expander("🗑️ 重置所有数据"):
        confirm = st.text_input("输入 RESET 确认", key="reset_confirm")
        if st.button("确认清空（不可恢复）", type="secondary"):
            if confirm == "RESET":
                storage.reset_data()
                st.success("已重置")
                st.rerun()
            else:
                st.error("请输入 RESET 确认")

    # ====== 关于 ======
    st.markdown("---")
    st.caption("🍳 Cook v1.0 · 个人厨房 App · DeepSeek 驱动")
    st.caption("数据存储位置：本地 JSON + GitHub Gist（可选）")
