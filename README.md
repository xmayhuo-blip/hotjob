# hotjob —— 最新出炉岗位即时查询

实时获取各大科技公司招聘网站的岗位列表及**精确发布时间**，帮助求职者第一时间发现新发布的岗位。

## 功能

- **最新岗位**：聚合 10 家公司的在招岗位，按发布时间排序，支持按公司、城市、岗位职能、时间范围筛选
- **链接查时间**：粘贴岗位链接，查询该岗位的精确发布时间及距今天数
- **发布时间统计**：今日 / 近 3 天 / 近 7 天 / 近 30 天岗位数量一览

## 覆盖公司

| 公司 | 招聘平台 |
|------|---------|
| 腾讯 | careers.tencent.com |
| 字节跳动 | jobs.bytedance.com |
| 阿里巴巴 | talent.alibaba.com |
| DeepSeek | Moka (high-flyer) |
| 智谱AI | 飞书招聘 |
| 月之暗面 | Moka |
| MiniMax | 飞书招聘 |
| 快手 | zhaopin.kuaishou.cn |
| 莉莉丝 | 飞书招聘 |
| 库洛游戏 | 飞书招聘 |

## 使用提示

- 默认展示「近 7 天」岗位；部分公司（如 DeepSeek、智谱 AI）近期新帖较旧，列表为空时，把顶部「时间」筛选调到「全部时间」即可查看（详情页有对应提示与一键按钮）。
- 发布时间直接来自各公司 ATS 系统；腾讯、快手展示的「更新时间」即行业内真实发布时间，最为可信。
- 数据仅作求职参考。

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

> 完整的原始审计 / QA / 评估记录存放在项目中 `[INTERNAL]` 标记的文件中，仅供历史追溯。
>
## License

MIT. 详见 [LICENSE](LICENSE)。
