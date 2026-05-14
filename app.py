"""
Cook · 个人厨房 App
- Streamlit 单页应用
- 移动端优先
- 底部 Tab Bar 导航
"""

import streamlit as st
from streamlit_option_menu import option_menu

from core import storage
from core.utils import today_str

# ============ 页面配置 ============
st.set_page_config(
    page_title="Cook · 我的厨房",
    page_icon="🍳",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ============ 移动端 CSS ============
st.markdown(
    """
<style>
/* 隐藏 Streamlit 默认元素，最大化内容区 */
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    padding-top: 1rem;
    padding-bottom: 6rem;  /* 给底部导航留空间 */
    padding-left: 1rem;
    padding-right: 1rem;
    max-width: 600px;
}

/* 按钮加大点击区域 */
.stButton button {
    min-height: 44px;
    font-size: 16px;
    border-radius: 10px;
}

/* 输入框加大 */
input, textarea, select {
    font-size: 16px !important;
}

/* 卡片样式 */
.cook-card {
    background: #FFF;
    border: 1px solid #F0F0F0;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04);
}
.cook-card-warn { border-left: 4px solid #FF6B35; }
.cook-card-ok { border-left: 4px solid #4CAF50; }
.cook-card-info { border-left: 4px solid #2196F3; }

.cook-tag {
    display: inline-block;
    padding: 2px 10px;
    background: #FFF0E6;
    color: #FF6B35;
    border-radius: 12px;
    font-size: 12px;
    margin-right: 4px;
}

.cook-danger { color: #E53935; font-weight: 600; }
.cook-warn { color: #FF9800; }
.cook-ok { color: #4CAF50; }
.cook-muted { color: #999; font-size: 13px; }

/* 底部导航容器 */
.bottom-nav {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: #FFF;
    border-top: 1px solid #EEE;
    z-index: 999;
    padding: 4px 0;
}

/* 让 option_menu 在底部容器内显示 */
div[data-testid="stHorizontalBlock"] .nav-link {
    font-size: 12px !important;
}

/* 大按钮 */
.big-btn button {
    height: 60px !important;
    font-size: 18px !important;
}

/* 标题间距收紧 */
h1, h2, h3 { margin-top: 0.5rem; margin-bottom: 0.8rem; }
h1 { font-size: 22px; }
h2 { font-size: 18px; }
h3 { font-size: 16px; }

/* metric 等控件适配 */
[data-testid="stMetricValue"] { font-size: 20px; }
</style>
""",
    unsafe_allow_html=True,
)


# ============ 密码门 ============
def _password_gate() -> bool:
    """简单密码保护，防止陌生人访问消耗 API"""
    try:
        required = st.secrets.get("APP_PASSWORD", "")
    except Exception:
        required = ""
    if not required:
        return True  # 未设置密码 = 不启用

    if st.session_state.get("auth_ok"):
        return True

    st.title("🍳 Cook · 我的厨房")
    st.caption("请输入访问密码")
    pwd = st.text_input("密码", type="password", key="pwd_input")
    if st.button("进入", use_container_width=True, type="primary"):
        if pwd == required:
            st.session_state.auth_ok = True
            st.rerun()
        else:
            st.error("密码错误")
    return False


# ============ 路由 ============
def main():
    if not _password_gate():
        st.stop()

    # 启动时加载数据（带 Gist 拉取）
    if "data_loaded" not in st.session_state:
        with st.spinner("加载数据中..."):
            storage.load_data(force_remote=True)
        st.session_state.data_loaded = True

    # 当前页面（默认首页）
    if "nav" not in st.session_state:
        st.session_state.nav = "首页"

    # 渲染对应页面
    page = st.session_state.nav
    if page == "首页":
        from views.home import render
        render()
    elif page == "菜谱":
        from views.recipes import render
        render()
    elif page == "冰箱":
        from views.inventory import render
        render()
    elif page == "购物":
        from views.shopping import render
        render()
    elif page == "我的":
        from views.settings import render
        render()

    # ============ 底部 Tab Bar ============
    st.markdown('<div class="bottom-nav">', unsafe_allow_html=True)
    selected = option_menu(
        menu_title=None,
        options=["首页", "菜谱", "冰箱", "购物", "我的"],
        icons=["house", "book", "snow", "cart", "gear"],
        default_index=["首页", "菜谱", "冰箱", "购物", "我的"].index(st.session_state.nav),
        orientation="horizontal",
        key="bottom_nav",
        styles={
            "container": {"padding": "0!important", "background-color": "#FFF"},
            "icon": {"color": "#666", "font-size": "20px"},
            "nav-link": {
                "font-size": "12px",
                "text-align": "center",
                "margin": "0px",
                "padding": "8px 4px",
                "color": "#666",
            },
            "nav-link-selected": {
                "background-color": "#FFF0E6",
                "color": "#FF6B35",
                "font-weight": "600",
            },
        },
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if selected != st.session_state.nav:
        st.session_state.nav = selected
        st.rerun()


if __name__ == "__main__":
    main()
