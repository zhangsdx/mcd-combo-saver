# WorkBuddy 开发上下文（workbuddy.md）

> 本文件用于麦当劳程序员创意开发大赛「WorkBuddy 专项奖励」核验，记录本项目在 WorkBuddy 中从需求到发布的真实开发上下文。项目本身为 WorkBuddy Skill，开发过程亦全程使用 WorkBuddy 智能体协作完成。

## 1. 需求与约束澄清

- 用户目标：参加「麦当劳程序员创意开发大赛」，基于麦当劳 MCP 开发一个开源 Skill，按 Star 排名，截止 2026-10-25 23:59。
- 硬性交付：仓库须含 `README.md` / `CONTEST_DECLARATION.md`（内容不可改）/ `MCP_INTEGRATION.md` / 源代码 / `workbuddy.md`，且 `mcp-config.example.json` 只用环境变量占位符。
- 创意方向：经与用户确认，选择「麦门省钱组合器」——预算约束下的餐品组合优化，差异化于已有的省钱/运势/隐藏吃法类作品。

## 2. 规则与能力调研（WorkBuddy 联网检索 + 读取官方仓库）

- 在 WorkBuddy 中检索并读取官方仓库 `M-China/mcd-developer-innovation-challenge` 的 `activityGuidelines.md`、`README.md` 与 `CONTEST_DECLARATION.md`，确认文件清单与报名 Issue 格式。
- 读取 `M-China/mcd-mcp-server` 的 `README.md`，获取接入地址 `https://mcp.mcd.cn`、Streamable HTTP 协议、Bearer 鉴权，以及完整 Tool 清单（含 `query-meals`、`calculate-price`、`query-store-coupons`、`list-nutrition-foods` 等），作为 `MCP_INTEGRATION.md` 的真实依据。

## 3. 方案设计

- 将「省钱点餐」建模为**带约束的组合优化**：输入预算/人数/去辣/必含饮料/取餐方式，对真实菜单做枚举与排序，再用 `calculate-price` 核真实到手价。
- 双形态交付：① `SKILL.md`——WorkBuddy 连接器形态，由智能体调用 `mcd-mcp` 工具完成真实流程；② `mcd_combo_saver.py`——可独立运行的参考 CLI，内置 mock 菜单（无 Token 可演示）与真实 MCP 客户端（配 Token 直连）。

## 4. 实现要点（WorkBuddy 辅助编写与自检）

- `SKILL.md`：定义触发词、前置校验、输入参数表、六步真实 MCP 调用流程、结构化输出格式与合规边界（默认只查询核价不支付）。
- `mcd_combo_saver.py`：组合枚举算法（套餐 / 主食+小食+饮料 / 主食+饮料 / 加甜品升级）、打分排序、mock 与真实双模式；真实客户端实现 Streamable HTTP 的 JSON-RPC（含 SSE 解析与 Session-Id 处理）。
- 在 WorkBuddy 中执行 mock 模式冒烟测试，确认算法输出 Top3 且无异常（见下方示例）。

### mock 冒烟测试示例

```
$ python mcd_combo_saver.py --mock --budget 40 --people 1
方案 1 ｜ 菜单小计 ¥39.0 ｜ 真实到手 ¥39.0 ｜ 结余 ¥1.0
   - 麦辣鸡腿堡套餐(中薯+中可) ¥39.0  [套餐]
方案 2 ｜ 菜单小计 ¥37.0 ｜ 真实到手 ¥37.0 ｜ 结余 ¥3.0
   - 双层吉士汉堡 ¥23.0  [主食]
   - 中薯条 ¥12.0  [小食]
   - 可口可乐(中) ¥10.0  [饮料]
方案 3 ｜ 菜单小计 ¥35.0 ｜ 真实到手 ¥35.0 ｜ 结余 ¥5.0
   - 巨无霸 ¥24.0  [主食]
   - 麦乐鸡(5块) ¥13.0  [小食]  ← 预算内无更便宜饮料时退化为主食+小食
结论: 最推荐【方案 1】...
```

## 5. 真实 MCP 端到端验证（2026-10-22）

为佐证「真实使用麦当劳 MCP」（大赛与 WorkBuddy 专项奖励核验要求），已用真实 Token 在 WorkBuddy 沙箱完成端到端调用：

- `query-nearby-stores`（深圳·福田）→ 真实门店 `1420450`；`query-meals` → **96 个在售餐品 / 15 分类**；
- `calculate-price` 核价（金额单位「分」，已换算为元）：不素之霸双层牛堡 + 纯牛奶 → 返回 `price=3750` 分 = **¥37.5**；
- 端到端输出三方案：极致省钱 ¥23.4 / 套餐省事 ¥22.9 / 吃饱实惠 ¥40.0；
- `query-store-coupons` 该门店返回空（已降级）；`list-nutrition-foods` 服务端暂未开放（已降级说明）。

MCP 客户端由 `requests` 改为标准库 `urllib` 实现，**零第三方依赖**，便于参赛者直接运行、评审复现。

## 6. 合规与发布

- `CONTEST_DECLARATION.md` 原样使用官方内容；仓库内无任何真实 Token/密钥，配置仅 `${MCD_MCP_TOKEN}` 占位符。
- 通过 WorkBuddy 协助创建公开 GitHub 仓库、提交全部文件，并按官方格式发布报名 Issue（标题与正文间不加换行、项目地址用纯文本 URL）。

## 6. 与 WorkBuddy 的联动价值

- 本项目**本身即 WorkBuddy Skill**，且开发全程由 WorkBuddy 智能体完成调研、编码、自检与发布，符合「真实使用腾讯 WorkBuddy 智能体」的专项奖励条件。
