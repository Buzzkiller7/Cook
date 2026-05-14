# 🍳 Cook · 个人厨房 App

一个住在手机里、能记住你冰箱、能听懂你说话的私人厨房管家。基于 Streamlit + DeepSeek 构建。

## ✨ 核心功能

- 📖 **菜谱管理**：增删改查、标签筛选、份数缩放、做菜模式（步骤化引导）
- 🧊 **冰箱库存**：分区显示、临期提醒、AI 语音/小票批量入库
- 🛒 **购物清单**：从菜谱一键加入、记一笔临时项、采购完成自动入库、常买快捷库
- 📝 **做菜待办**：完成后智能扣减冰箱库存（AI 处理"一撮""一勺"等模糊用量）
- 🤖 **AI 智能体**：
  - 随口说一句 → 自动生成结构化菜谱
  - 基于冰箱现有食材推荐今晚菜（优先临期食材）
  - 口语描述/小票文字 → 结构化入库
  - 智能保质期估算

## 🚀 快速开始

### 1. 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 secrets
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# 编辑 secrets.toml，填入你的 DeepSeek API Key

# 启动
streamlit run app.py
```

浏览器打开 http://localhost:8501，手机访问局域网 IP:8501 即可。

### 2. Streamlit Community Cloud 部署（推荐）

1. **把本目录推到 GitHub**（公开或私有仓库都行）

   ```bash
   git init
   git add .
   git commit -m "init cook app"
   git remote add origin <your-repo>
   git push -u origin main
   ```

   注意 `.streamlit/secrets.toml` 已在 `.gitignore` 中，**不会被提交**。

2. **登录 https://share.streamlit.io**，点 New app

3. **选择你的仓库 + 主文件 `app.py`**

4. **在 App settings → Secrets 中粘贴**：

   ```toml
   DEEPSEEK_API_KEY = "sk-..."
   DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
   APP_PASSWORD = "你想设置的密码"

   # 可选：多设备同步
   GITHUB_TOKEN = "ghp_..."
   GIST_ID = "your_gist_id"
   ```

5. **手机收藏到主屏幕**：用 Safari/Chrome 打开部署后的 URL，菜单 → "添加到主屏幕"，体验接近原生 App。

### 3. 配置多设备同步（GitHub Gist，可选但推荐）

1. https://github.com/settings/tokens → Generate new token → 勾选 `gist` 权限
2. https://gist.github.com → New gist → 文件名填 `cook_data.json`，内容随意（比如 `{}`），创建 **Secret gist**
3. 从 gist URL 中复制 ID（形如 `https://gist.github.com/yourname/<这一串就是id>`）
4. 把 token 和 gist id 填到 Streamlit Secrets 即可

之后你在手机和电脑访问同一个 Streamlit URL，数据实时同步。

## 📁 项目结构

```
Cook/
├── app.py                    # 入口，含底部导航
├── core/
│   ├── storage.py            # 存储层（本地 JSON + Gist 同步）
│   ├── llm.py                # DeepSeek 封装 + 5 大场景
│   └── utils.py              # 工具函数
├── views/
│   ├── home.py               # 首页 Dashboard
│   ├── recipes.py            # 菜谱
│   ├── inventory.py          # 冰箱
│   ├── shopping.py           # 购物
│   └── settings.py           # 设置
├── data/                     # 本地数据缓存
├── .streamlit/
│   ├── config.toml           # 主题色
│   └── secrets.toml          # 密钥（不进 git）
└── requirements.txt
```

## 🎯 使用流程示例

```
新建/AI生成菜谱（番茄炒蛋）
   │
   ↓
加入购物清单（番茄2个、鸡蛋3个）
   │
   ↓
去超市，对照清单买，勾选已买
   │
   ↓
回家点"采购完成 → 入库"，自动添加到冰箱
   │
   ↓
首页 AI 推荐今晚菜（基于冰箱）
   │
   ↓
加入做菜待办 → 立即做菜（做菜模式）
   │
   ↓
完成 → AI 智能扣减库存
```

## 🛠️ 技术栈

- **前端 / UI**：Streamlit + streamlit-option-menu
- **LLM**：DeepSeek API（OpenAI 兼容协议）
- **存储**：JSON 文件 + GitHub Gist 同步
- **部署**：Streamlit Community Cloud（免费）

## 📝 数据模型

所有数据存为一个 JSON 文件：

```json
{
  "recipes": [...],              // 菜谱
  "inventory": [...],            // 冰箱库存
  "shopping": [...],             // 购物清单
  "tasks": [...],                // 做菜待办
  "frequent_ingredients": [...], // 常买快捷库
  "meta": { "last_synced_at": "..." }
}
```

## 🔒 安全

- API Key 通过 Streamlit Secrets 注入，不进 git
- 可选的密码门防止陌生人访问消耗你的 API 额度
- Gist 用 Secret Gist + Personal Access Token 鉴权

## 📌 路线图

- [x] v1.0：核心闭环 + AI 加持
- [ ] v1.1：菜谱图片上传
- [ ] v1.2：周计划/食谱排班
- [ ] v1.3：小票拍照识别（多模态）

---

🤖 由 Claude 协助设计与实现
