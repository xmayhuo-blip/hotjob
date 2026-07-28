# [INTERNAL] 项目开发审计记录
> 本文档已归档到项目内部记录。对公开访客而言，核心信息已在 README 和 CONTRIBUTING.md 中覆盖。
>
# 项目整体检查报告

> 2026-07-26 | 9 家 MVP 公司 | Python + 原生前端

## 一、已修复 P0 事故（3 个）

| # | 根因类别 | 描述 | 修复 |
|---|---------|------|------|
| 1 | Python 作用域 | `_last_refresh` 缺 `global` 声明 → 永远显示 `--:--` | 加 `global` |
| 2 | 类型陷阱 | `jid="0"` → `if "0"` 为 True → URL 生成 `?positionId=0` → 重定向首页 | `and jid.isdigit() and jid != "0"` |
| 3 | CSS 硬编码 | `max-height:520px` → JD 长内容被截断 | `max-height: calc(100vh - 92px)` |

## 二、归纳总结

### 今天踩过的坑

```
1. Python: 函数内赋值模块级变量必须 global
   → 新规则：任何函数内 = 开头的 `_xxx =` 都检查是否模块级变量

2. Python: `if "0"` is True
   → 新规则：字符串 ID 用于 URL 构造前，必须 `isdigit()` + `!= "0"`

3. CSS: 永远不要 hardcode 固定 px 高度
   → 新规则：content 容器用 `flex: 1; min-height: 0; overflow-y: auto`

4. 数据信任: 取不到时不伪造
   → 已移除演示数据，诚实展示"暂无数据"
```

### 预防 checklist（每次改代码必查）

```
[ ] 函数内是否有 `_xxx = time.time()`？→ 检查 global 声明
[ ] 是否有 `if str_id` 且随后用于 URL？→ 检查 isdigit() + != "0"
[ ] 是否有固定 px 的 height/max-height？→ 改用 vh/calc/flex
[ ] 新增字段是否缺回退值？→ GET 必须带 default
[ ] parser 是否漏了 HIRING_RADAR_INSECURE？→ 检查 SSL 上下文
[ ] 改了 xxx 是否影响链接/日期/筛选？→ 回归对应的 API endpoint
```

## 三、项目现状

| 维度 | 状态 |
|------|:----:|
| 9 家 parser 连通 | ✅ |
| 定时刷新 + 缓存 | ✅ |
| 失败重试 | ✅ |
| 公司筛选 | ✅ |
| 城市/日期/类型/职类/经验筛选 | ✅ |
| 岗位详情（职责+要求分区） | ✅ |
| 详情滚动容器 | ✅ |
| 投递链接准确性 | ✅ |
| 更新时间显示 | ✅ |
| 结果计数 | ✅ |
| 冷启动自动重试 | ✅ |
| 数据真实性（无伪造） | ✅ |
| nginx/gunicorn/Docker | ✅ |

## 四、残留风险

| 风险 | 等级 | 说明 |
|------|:----:|------|
| 快手 SSL | 🟡 低 | 已加 HIRING_RADAR_INSECURE，但未验证 |
| 米哈游/叠纸 | 🟡 低 | 需独立 parser，当前已移除 |
| 并发槽位 | 🟢 无 | 3 并发 + 限流，安全 |
| CSS 响应式 | 🟢 无 | 移动端已适配 |

## 五、后续迭代建议

1. 每次新增代码 → 先跑 checklist → 再冒烟测试 → 再提交
2. 写 `parsers/tests/test_all.py` — 自动化 parser 冒烟
3. 前端加 loading skeleton 替代空白等待
4. 加手动「立即刷新」按钮（当前只能等整点）
