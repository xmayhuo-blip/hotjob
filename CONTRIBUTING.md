# Contributing to hotjob

## 项目结构

```
hotjob/
├── parsers/             # 招聘网站解析器（每家公司一个 fetch 函数）
│   ├── loader.py        # 统一加载器，10 家 MVP 公司直连
│   ├── tencent.py       # 示例：独立 parser
│   ├── feishu.py        # 飞书招聘通用解析器
│   └── moka.py          # Moka 摩卡通用解析器
├── web/
│   ├── app.py           # HTTP 服务器 + 业务逻辑
│   ├── index.html       # 单页前端
│   └── stats.py         # 页面访问量统计
├── tests/
│   ├── test_utils.py    # 单元测试（纯逻辑）
│   ├── test_sanity.py   # 数据真实性测试（需网络）
│   └── test_e2e.py      # 端到端链路验证
└── hiring_radar.py      # CLI 工具（解析器引擎）
```

## 新增一家公司

### 如果使用飞书招聘 / Moka

编辑 `parsers/loader.py`，在 `PARSER_CONFIG` 中添加一行：

```python
"newco": ("parsers.feishu", "fetch", ("newco.jobs.feishu.cn", "公司名")),
```

然后在 `web/app.py` 的 `_build_companies()` 中添加前端配置：

```python
"newco": {"name": "公司名", "color": "#HEX", "url": "https://...", "recruit_type": "社招", "max_count": 400},
```

同时更新 `MIN_JOBS_THRESHOLD` 和 `MIN_PER_COMPANY`（test_sanity.py / test_e2e.py）。

### 如果是自建 ATS

1. 在 `parsers/` 下创建 `newco.py`，实现 `fetch(keyword="", ...) → list[dict]`
2. 每个 dict 必须含字段：`title`, `company`, `location`, `dept`, `date`, `jd`, `url`, `id`
3. 在 `parsers/loader.py` 注册
4. 在 `web/app.py` 注册前端配置

## 本地运行

```bash
pip install -r requirements.txt
cd web && python app.py
# 打开 http://localhost:8787
```

## 测试

```bash
# 单元测试（离线）
python3 tests/test_utils.py

# 数据真实性测试（需网络）
HIRING_RADAR_INSECURE=1 python3 tests/test_sanity.py

# 端到端验证（需服务器运行中）
python3 tests/test_e2e.py http://localhost:8787
```

## 数据格式说明

所有 parser 输出统一 schema：

| 字段 | 必填 | 说明 |
|------|------|------|
| title | 是 | 岗位名称 |
| company | 是 | 公司名称 |
| location | 是 | 工作地点 |
| dept | 是 | 部门 |
| date | 是 | 发布时间（精确到日） |
| jd | 是 | 岗位描述全文 |
| url | 是 | 岗位详情页链接 |
| id | 是 | 唯一标识 |

## PR 流程

1. 确保新增 parser 后 `tests/test_sanity.py` 全量通过
2. 确保 `tests/test_utils.py` 20/20 通过
3. PR 描述中说明新增的公司名、ATS 类型、数据量
