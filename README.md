# OfferBoast 岗位雷达

实时获取各大科技公司招聘网站的岗位列表及**精确发布时间**，帮助求职者第一时间发现新发布的岗位。

## 功能

- **最新岗位**：聚合 9 家公司的在招岗位，按发布时间排序，支持按公司、城市、岗位职能、时间范围筛选
- **链接查时间**：粘贴岗位链接，查询该岗位的精确发布时间及距今天数
- **发布时间统计**：今日 / 近 3 天 / 近 7 天 / 近 30 天岗位数量一览

## 覆盖公司

| 公司 | 招聘平台 |
|------|---------|
| 腾讯 | careers.tencent.com |
| 字节跳动 | jobs.bytedance.com |
| 小红书 | job.xiaohongshu.com |
| 阿里巴巴 | talent.alibaba.com |
| DeepSeek | Moka (high-flyer) |
| 智谱AI | 飞书招聘 |
| 月之暗面 | Moka |
| MiniMax | 飞书招聘 |
| 快手 | zhaopin.kuaishou.cn |

## 技术架构

- **后端**：纯 Python 标准库（`http.server`），唯一外部依赖 `pycryptodome`（Moka 解密）
- **前端**：单文件 SPA（原生 HTML/CSS/JS，无框架）
- **解析器**：每家公司一个独立 parser，统一输出 schema
- **缓存**：10 分钟内存缓存 + 请求去重 + 启动预热，支持 100 人并发
- **部署**：支持 Render（`render.yaml` + `Procfile`）

## 本地运行

```bash
pip install -r requirements.txt
python web/app.py
# 打开 http://localhost:8787
```

## License

MIT
