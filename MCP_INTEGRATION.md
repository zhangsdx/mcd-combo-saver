# MCP 集成说明（MCP_INTEGRATION）

## 1. 实际使用的麦当劳 MCP Server

| 项 | 值 |
|---|---|
| Server 名称 | `mcd-mcp`（麦当劳中国官方 MCP） |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP（`type: streamablehttp`） |
| 鉴权 | `Authorization: Bearer ${MCD_MCP_TOKEN}`（环境变量占位符，见 `mcp-config.example.json`） |
| 频率限制 | 每 Token 600 次/分钟（429 限流） |

> 官方仓库与文档：<https://github.com/M-China/mcd-mcp-server>，开放平台 <https://open.mcd.cn/mcp>。

## 2. 实际调用的 Tools（按使用顺序）

| Tool | 用途 | 在 Skill 中的角色 |
|---|---|---|
| `query-nearby-stores` | 查询附近可用门店 | 定位门店，取得 `storeCode` |
| `delivery-query-stores` / `delivery-query-addresses` | 外送场景门店与地址 | 外送模式下替代上述工具 |
| `query-meals` | 查询当前可售餐品列表（分类/编码/标签/价格） | 拉取真实菜单，作为组合求解输入 |
| `query-meal-detail` | 查询套餐组成与可替换项 | 解析套餐内容、判断可换品 |
| `query-store-coupons` | 查询当前门店可用优惠券 | 为每个候选组合匹配可用券 |
| `calculate-price` | 商品价格计算（含优惠/配送费/应付） | **真实到手价的唯一权威来源** |
| `list-nutrition-foods` | 餐品营养信息 | 为 Top 组合补能量/蛋白（可选） |
| `campaign-calendar` | 当月营销活动日历 | 提示可叠加的省钱活动（可选） |
| `now-time-info` | 当前时间 | 辅助判断活动/供应时段（可选） |

## 3. 调用流程

```
用户需求(预算/人数/约束/地址)
        │
        ▼
[1] query-nearby-stores ──► storeCode
        │
        ▼
[2] query-meals(storeCode) ──► 真实菜单(分类/价格/标签)
        │   约束过滤(去辣/必含饮料)
        ▼
[3] 本地组合枚举 + 排序(预算内, 品类覆盖/单价打分)
        │   Top 候选
        ▼
[4] query-store-coupons(storeCode) ──► 可用券
        │
        ▼
[5] calculate-price(storeCode, mealType, items[], coupons)
        │
        ▼
[6] (可选) list-nutrition-foods / campaign-calendar
        │
        ▼
输出 Top3 方案: 餐品清单 / 菜单小计 / 真实到手价 / 结余 / 营养 / 取舍建议
```

## 4. 业务价值

- **真实可用，不是玩具**：菜单、价格、优惠券、到手价全部来自官方 MCP 实时数据，`calculate-price` 是核价权威，避免「自估价格」误导用户。
- **把点餐变成带约束的优化问题**：在预算上限与硬约束（人数/去辣/必含饮料/取餐方式）下枚举组合并排序，解决「选择困难 + 想省钱」的真实痛点。
- **可解释**：每个方案给出明细、结余与一句话取舍建议，用户看得懂为什么推荐。
- **合规安全**：默认只查询+核价+推荐，不领券/不下单/不支付；Token 仅以环境变量占位符存在，不落库不泄密。
