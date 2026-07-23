# OfferBoast 岗位雷达 — 部署指南

## 前置条件

- GitHub 账号
- Render 账号（https://render.com，免费注册）

## 方案对比

| 方案 | 免费额度 | 改动量 | HTTPS | 推荐度 |
|------|---------|--------|-------|--------|
| **Render** | 750h/月 | 零（已就绪） | 自动 | ⭐⭐⭐⭐⭐ |
| Railway | $5 试用额度 | 零 | 自动 | ⭐⭐⭐⭐ |
| Fly.io | 3 台共享 VM | 需 Dockerfile | 自动 | ⭐⭐⭐ |
| VPS 自建 | 无 | 需配 Nginx | 需手动 | ⭐⭐ |

---

## 方案一：Render 部署（推荐，约 10 分钟）

### 第 1 步：推送到 GitHub

```bash
cd Hiring-Radar

# 初始化 Git 仓库
git init
git add .
git commit -m "OfferBoast 岗位雷达 — 初始版本"

# 创建 GitHub 仓库后执行
git remote add origin https://github.com/<你的用户名>/offerboast.git
git branch -M main
git push -u origin main
```

需要上传的文件结构：
```
Hiring-Radar/
├── web/
│   ├── app.py              # Web 服务器
│   ├── index.html          # 前端页面
│   ├── favicon.ico         # 猴子图标
│   ├── favicon-*.png       # 多尺寸图标
│   └── apple-touch-icon.png
├── parsers/                # 招聘网站解析器
│   ├── bytedance.py
│   ├── tencent.py
│   ├── xiaohongshu.py
│   ├── alibaba.py
│   ├── feishu.py
│   ├── moka.py
│   ├── kuaishou.py
│   └── companies.seed
├── hiring_radar.py         # 核心引擎
├── requirements.txt        # Python 依赖
├── Procfile                # 启动命令
└── render.yaml             # Render 配置
```

### 第 2 步：在 Render 创建 Web Service

1. 打开 https://dashboard.render.com
2. 点击 **New +** → **Web Service**
3. 连接你的 GitHub 仓库
4. 配置：
   - **Name**: `offerboast-job-radar`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `cd web && python app.py`
   - **Plan**: `Free`
5. 点击 **Create Web Service**

### 第 3 步：等待部署完成

- Render 会自动安装依赖、启动服务
- 部署完成后获得公网地址：`https://offerboast-job-radar.onrender.com`
- 浏览器打开即可使用，自动 HTTPS

### 或者：使用 render.yaml 一键部署

1. 将 `render.yaml` 推到 GitHub 仓库根目录
2. 在 Render Dashboard 点击 **New +** → **Blueprint**
3. 选择仓库，Render 自动读取 `render.yaml` 配置
4. 点击 **Apply** 即可

---

## 方案二：Railway 部署

1. 打开 https://railway.app
2. **New Project** → **Deploy from GitHub repo**
3. 选择仓库，Railway 自动检测 `Procfile`
4. 自动部署，获得 `xxx.up.railway.app` 地址

---

## 本地测试（部署前验证）

```bash
# 确保依赖已安装
pip install -r requirements.txt

# 启动服务
cd web && python app.py

# 验证
curl http://localhost:8787/api/health
# 应返回 {"status": "ok", ...}
```

---

## 已完成的部署适配

以下改动已生效，代码可直接部署：

1. **PORT 环境变量**：`PORT = int(os.environ.get("PORT", "8787"))` — Render 会注入 PORT
2. **Python 路径**：`PYTHON_BIN = sys.executable` — 不再硬编码本地路径
3. **环境变量传递**：移除硬编码 PATH，使用 `os.environ.copy()`
4. **requirements.txt**：`pycryptodome>=3.20.0`（Moka AES 解密依赖）
5. **Procfile**：`web: cd web && python app.py`
6. **render.yaml**：含健康检查、自动部署配置
7. **静态文件服务**：favicon/图标通过 app.py 内置 serving

## 注意事项

- Render 免费版服务 15 分钟无请求会自动休眠，首次唤醒约需 30 秒
- 9 家公司并行拉取约需 5-6 秒，首次加载可能稍慢
- 5 分钟内存缓存生效后，后续请求秒回
- 如需更高可用性，可升级到 Render 付费版（$7/月起，不休眠）
