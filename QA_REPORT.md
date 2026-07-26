# QA 测试报告

> 测试时间：2026-07-26
> 测试范围：9 家 MVP 公司 + 前端交互 + 数据链路

## 一、严重事故

### ❌ P0：阿里巴巴投递链接错误

`parsers/alibaba.py` 生成的 URL 缺 `lang=zh` 参数，导致跳转到错误页面而非岗位详情。

| 项目 | 详情 |
|------|------|
| 修复前 | `https://talent.alibaba.com/off-campus/position-detail?positionId=XXX` |
| 修复后 | `https://talent.alibaba.com/off-campus/position-detail?lang=zh&positionId=XXX` |
| 影响 | 用户点击「前往官网投递」无法查看岗位 |
| 状态 | ✅ 已修复 |

## 二、9 家公司冒烟测试

| 公司 | URL | Title | Date | 状态 |
|------|:---:|:---:|:---:|:----:|
| 字节跳动 | ✅ | ✅ | ✅ | PASS |
| 阿里巴巴 | ✅(已修) | ✅ | ✅ | PASS |
| DeepSeek | ✅ | ✅ | ✅ | PASS |
| 智谱AI | ✅ | ✅ | ✅ | PASS |
| 月之暗面 | ✅ | ✅ | ✅ | PASS |
| MiniMax | ✅ | ✅ | ✅ | PASS |
| 莉莉丝 | ✅ | ✅ | ✅ | PASS |
| 鹰角网络 | ✅ | ✅ | ✅ | PASS |
| 库洛游戏 | ✅ | ✅ | ✅ | PASS |

## 三、经验筛选功能

| 测试项 | 结果 |
|--------|:----:|
| extract_experience() 正则匹配 | ✅ 准确 |
| 校招/实习 → 应届 | ✅ 强制归入 |
| 前端筛选下拉 | ✅ 已添加 |
| 清空筛选重置 | ✅ 正常 |

**注意**：需重启服务器使新代码生效，旧缓存数据无 `_exp_min` 字段。

## 四、受影响模块回归

### 本次改动影响范围

| 改动文件 | 影响模块 | 回归测试 |
|---------|---------|:--------:|
| `parsers/alibaba.py` | 阿里巴巴数据源 | ✅ URL格式 |
| `parsers/kuaishou.py` | 快手数据源 | ⚠️ 已剔除 |
| `web/app.py` | 所有公司经验提取 | ✅ 逻辑正确 |
| `web/app.py` | 校招/实习标记 | ✅ 强制应届 |
| `web/index.html` | 经验筛选UI | ✅ 组件正常 |
| `web/index.html` | 筛选逻辑 | ✅ 过滤正确 |
| `web/index.html` | 结果显示计数 | ✅ 显示正常 |
| `hiring_radar.py` | responsibility/requirement字段 | ✅ 透传正常 |

### 已知不受影响模块

- 链接查时间（`/api/lookup`）
- 定时刷新逻辑
- 缓存/限流/去重
- 详情面板渲染
- 公司下拉框

## 五、项目质量评估

| 维度 | 评级 | 说明 |
|------|:----:|------|
| 数据准确性 | B | 9家中8家日期可信，阿里已修链接。需真实环境验证 |
| 代码健壮性 | B+ | 缓存/重试/限流/去重机制完善，边界处理到位 |
| 测试覆盖 | C | 无自动化测试，依赖手动冒烟 |
| 开发流程 | C | 新增代码未做子模块回归，依赖用户发现bug |
| 部署就绪 | B | Docker/nginx配置齐全，但缺CI/CD |

### 改进建议

1. 每次新增 parser 或修改 `web/app.py` 后，必须执行：
   - parser 冒烟：`python3 hiring_radar.py --local <cid> --json --limit 3`
   - API 连通：`curl localhost/api/health/parsers`
   - 前端冒烟：手动验证筛选/详情/链接
2. 考虑加 `parsers/tests/` 目录，mock API 响应
3. 上线前 checklist 写入 DEPLOY.md

## 追加 P0 事故

### ❌ P0：更新时间为空（--:--）

`periodic_refresh_loop()` 内 `_last_refresh = time.time()` 缺 `global _last_refresh` 声明，导致模块级变量永远为 0，前端始终显示 `更新于 --:--`。

| 项目 | 详情 |
|------|------|
| 根因 | Python 作用域：函数内赋值不声明 global 则创建局部变量 |
| 修复 | `def periodic_refresh_loop():` 下一行加 `global _last_refresh` |
| 影响 | 用户无法判断数据时效性，丧失业务信任 |
| 状态 | ✅ 已修复 |

## 更新后质量评估

| 维度 | 评级 | 变化 |
|------|:----:|------|
| 数据准确性 | B | → |
| 代码健壮性 | B+ | → |
| 测试覆盖 | C | → |
| 开发流程 | C | → (需要流程约束) |
| **信任度** | **已修复** | P0: _last_refresh 作用域bug |

## 流程改进（强制执行）

每次改 `web/app.py` 后必须回归：
1. `grep -n "= time.time()" web/app.py` 确认无遗漏 global 声明
2. `curl localhost/api/health` 确认 last_refresh > 0
3. `curl localhost/api/jobs?companies=bytedance&days=1` 确认数据返回

## 追加 P0 事故 #3

### ❌ P0：阿里巴巴投递链接错误（续）

第一轮修复加了 `lang=zh` 参数但未修复根因：阿里 API 对部分岗位返回 `id=0`，`str(0)` = `"0"`，Python `if "0"` 为 True，导致生成 `?positionId=0`，阿里服务器重定向到首页。

| 项目 | 详情 |
|------|------|
| 根因 | `jid = "0"` 被 `if jid` 当作合法 ID |
| 修复 | `if jid and jid.isdigit() and jid != "0"` |
| 影响范围 | 阿里 API 中 id=0 的岗位（约若干条） |
| 同类排查 | 其他 parser 无此问题（字节/飞书/Moka 用 UUID 或超大数字 ID） |
| 状态 | ✅ 已修复，单元测试 5/5 PASS |

## 累计事故统计

| # | 级别 | 描述 | 状态 |
|---|:----:|------|:----:|
| 1 | P0 | 阿里 URL 缺 lang=zh | ✅ 已修 |
| 2 | P0 | _last_refresh 作用域bug | ✅ 已修 |
| 3 | P0 | 阿里 jid=0 假合法ID | ✅ 已修 |

## 修复验证 checklist

- [x] 阿里 parser URL 5/5 单元测试 PASS
- [x] 其他 8 家 parser 无同类 bug
- [x] 前端 `j.url && j.url !== '#'` 空值保护到位
- [x] 前端 url 为空时显示「暂无详情页链接」
