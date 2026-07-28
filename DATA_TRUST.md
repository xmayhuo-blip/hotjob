# [INTERNAL] 数据可信度记录
> 本文档内容的核心信息已整合到 README#数据来源。
>
# 数据可信度记录

## 可信公司（有明确首次发布时间）

| 公司 | 日期字段 | 语义 | 状态 |
|------|---------|------|------|
| 字节跳动 | `publish_time` | 首次发布时间戳(ms) | ✅ 上线 |
| 阿里巴巴 | `publishTime` | 首次发布时间，另有 `modifyTime` 独立字段 | ✅ 上线 |
| DeepSeek | `publishedAt` / `createdAt` | 优先 publishedAt，回退 createdAt | ✅ 上线 |
| 智谱AI | `publish_time` | 首次发布时间戳(ms) | ✅ 上线 |
| 月之暗面 | `publishedAt` / `createdAt` | Moka 发布时间 | ✅ 上线 |
| MiniMax | `publish_time` | 首次发布时间戳(ms) | ✅ 上线 |
| 莉莉丝 | `publish_time` | 飞书招聘发布时间 | ✅ 上线 |
| 鹰角网络 | `publishedAt` / `createdAt` | Moka 发布时间 | ✅ 上线 |
| 库洛游戏 | `publish_time` | 飞书招聘发布时间 | ✅ 上线 |

## 已剔除（日期不可信）

| 公司 | 日期字段 | 原因 |
|------|---------|------|
| 腾讯 | `LastUpdateTime` | 最后更新时间，非首次发布 |
| 快手 | `updateTime` | 更新时间，非首次发布 |
| 小红书 | `publishTime` | 唯一日期字段，API 无 create/update 区分，旧岗位刷新后日期被重置 |

## 待开发（0岗位或需新parser）

| 公司 | 原因 | 后续 |
|------|------|------|
| 米哈游 | jobs.mihoyo.com 是自建招聘系统，非 Moka | 需写独立 parser |
| 叠纸 | Moka 返回 0 岗位，orgId/siteId 待核实 | 核实后重新接入 |
