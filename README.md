# 觅图 mitu — AI 图片生成工具

基于 GPT Image 2 的 AI 图片生成桌面工具，支持文生图、图生图、实时监控等功能。

## 快速开始

1. **克隆项目**
   ```bash
   git clone https://github.com/Patrick-mufeng/image2-web.git
   cd image2-web
   ```

2. **配置 API Key**
   编辑 `.env` 文件，填入你的 API Key：
   ```
   YUNWU_API_KEY=sk-your-api-key-here
   YUNWU_BASE_URL=https://yunwu.ai
   ```
   > 注册获取 API Key：[云雾 API](https://yunwu.ai/register?aff=zM1f)

3. **启动服务**
   双击 `start.bat` 即可启动，浏览器自动打开 `http://localhost:8000`

> 项目已内置嵌入式 Python 3.11.9 + 所有依赖，无需手动安装 Python 环境。

---

## 功能特性

### 🎨 图片生成
- 支持 OpenAI 格式（gpt-image-2 / gpt-image-1 / DALL-E 3 等）
- 支持 Replicate 格式（FLUX Schnell / Dev / Pro）
- 5 种比例：1:1、16:9、9:16、4:3、3:4
- 3 级分辨率：1MP / 2MP / 4MP
- 独立提示词模式（每行各生成一张图）
- 风格模板库（22 套模板，13 种分类）
- 左提示词右结果的舒适布局

### 🖼️ 图生图
- 拖拽上传图片进行 AI 编辑
- 支持单图/多图编辑
- 可选蒙版上传（PNG 格式）
- 支持 gpt-image-2 / gpt-image-2-all 等模型

### 📜 生成历史
- 自动保存所有生成记录
- 网格展示，点击查看详情
- 支持修改提示词后重新生成

### 📚 案例展示
- 内置 487 个高质量案例（含中文提示词 274 条）
- 分类筛选 + 语言筛选（中文/English）
- 分页浏览，图片本地缓存加载

### 📡 实时监控
- 每步操作的实时日志流
- 请求/响应 JSON 完整展示
- 错误信息含完整请求上下文和服务器响应

### 💰 余额查询
- 一键查询 API Key 余额
- 显示令牌名称、本月用量、剩余额度
- 点击 Key 设置标签自动刷新

### 🖼️ 元数据编辑
- 拖拽图片批量修改 EXIF 信息
- PS 预设一键套用
- **💿 另存为预设** — 自定义预设永久保存
- 批量处理后打包下载 ZIP

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python FastAPI |
| 前端 | 纯 HTML + CSS + JS (SPA) |
| 存储 | JSON 文件 (data/ 目录) |
| 运行时 | 嵌入式 Python 3.11.9（无需系统安装 Python） |

---

## 项目结构

```
image2-web/
├── backend/
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py            # 配置管理
│   ├── models.py            # 数据模型
│   ├── routers/             # API 路由
│   │   ├── generation.py    # 文生图
│   │   ├── edits.py         # 图生图
│   │   ├── history.py       # 历史记录
│   │   ├── cases.py         # 案例展示
│   │   ├── metadata.py      # 元数据
│   │   ├── templates.py     # 风格模板
│   │   └── config_routes.py # 配置+余额查询
│   ├── services/            # 业务逻辑
│   │   ├── yunwu_client.py  # 云雾 API 客户端
│   │   ├── task_manager.py  # 异步任务管理
│   │   ├── history_store.py # 历史存储
│   │   ├── log_store.py     # 日志存储
│   │   └── ...
│   └── static/              # 前端静态文件
│       ├── index.html
│       ├── css/style.css
│       └── js/app.js
├── data/                    # 数据目录
│   ├── cases.json           # 案例库（487条）
│   ├── style-library.json   # 风格模板库
│   ├── case_images/         # 案例图片（453张）
│   └── user_presets.json    # 用户自定义预设
├── python/                  # 嵌入式 Python 3.11.9
├── start.bat                # 启动脚本
├── requirements.txt         # Python 依赖
└── .env.example             # 配置模板
```

---

## 设计风格

温暖极简（Warm Minimal）— 暖白 + 大地色系，浅色/深色主题切换（localStorage 持久化）。

---

## 版本

V3.0

---

## 作者

Patrick
