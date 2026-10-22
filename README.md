# 麦门省钱组合器（McD Combo Saver）

> 基于 **麦当劳 MCP** 的预算约束餐品组合优化 Skill —— 在给定预算与硬约束下，从麦当劳真实在售菜单中找出性价比最高的餐组合，并用官方 `calculate-price` 核出真实到手价。

[![基于麦当劳 MCP](https://img.shields.io/badge/基于-麦当劳%20MCP-orange)](https://open.mcd.cn/mcp)
[![WorkBuddy](https://img.shields.io/badge/官方合作伙伴-WorkBuddy-blue)](https://www.workbuddy.cn)
[![License: 参赛作品](https://img.shields.io/badge/license-活动参赛作品-green)]

---

## 一、项目简介

「麦门省钱组合器」是一个面向「选择困难 + 想省钱」场景的麦当劳点餐决策 Skill。它把点餐从「凭感觉凑单」变成「带约束的组合优化」：

- **预算上限**：你只说「今天 40 块」，它帮你把钱花在刀刃上；
- **硬约束**：人数、是否吃辣、必含饮料、取餐方式（自取/堂食/外送）；
- **真实数据**：菜单、价格、优惠券、到手价全部来自麦当劳官方 MCP 实时接口，不编造；
- **Top 3 方案 + 取舍建议**：每个方案给出菜单小计、优惠券后真实到手价、结余、营养概览与一句话建议。

## 二、功能亮点

| 能力 | 实现方式（真实 MCP 工具） |
|---|---|
| 定位门店 | `query-nearby-stores` / `delivery-query-stores` |
| 真实菜单 | `query-meals` + `query-meal-detail` |
| 约束求解 | 本地组合枚举与排序算法（预算内、去辣、必含饮料） |
| 优惠券核价 | `query-store-coupons` + `calculate-price`（官方报价） |
| 营养标注 | `list-nutrition-foods`（可选） |
| 活动提示 | `campaign-calendar`（可选） |

## 三、适用人群

- 想「花最少钱吃最饱」的学生 / 上班族；
- 有忌口（不吃辣）或控预算（每日餐饮封顶）的用户；
- 多人拼单、需要快速凑出人均最划算方案的用户。

## 四、快速开始

### 1. 申请麦当劳 MCP Token（免费）

打开 [open.mcd.cn/mcp](https://open.mcd.cn/mcp) → 手机号登录 → 右上角「控制台」→「激活」→ 复制 Token（32 位）。
> ⚠️ Token 等同于你的账号凭证，**只放在客户端私有配置或本机环境变量**，不要提交到任何仓库。

### 2. 在 WorkBuddy 配置 `mcd-mcp` 连接器

左侧边栏「专家 · 技能 · 连接器」→「连接器」→ 右上角「自定义连接器」→「配置 MCP」，粘贴 `mcp-config.example.json` 内容，把 `${MCD_MCP_TOKEN}` 换成你的 Token，保存并**启用**。

### 3. 安装本 Skill

```bash
# 把 skill 目录复制到用户级技能目录
cp -r . ~/.workbuddy/skills/mcd-combo-saver
```

重启 WorkBuddy 后，直接说：

> 「40 块，不辣，主食小食饮料各一份，自取，我在深圳福田。」

即可触发；也可输入 `/mcd-combo-saver` 激活。

### 4.（可选）命令行体验

```bash
pip install -r requirements.txt
export MCD_MCP_TOKEN=你的Token        # 真实模式；不填则用 --mock 演示
python mcd_combo_saver.py --mock --budget 40 --people 1
python mcd_combo_saver.py --mock --budget 80 --people 2 --no-spicy
```

## 五、使用示例（对话）

**用户**：35 元，不辣，有糖可乐去冰，带走，我在南京江宁区。先显示门店让我选，再查菜单给我最多三份方案，说明价格和取舍。没有满足条件的方案先别改饮料或加预算。只查询和核价，不领券不下单。

**麦门省钱组合器**：
1. 调用 `query-nearby-stores` 列出江宁区附近门店 → 请你确认门店；
2. 调用 `query-meals` 拉该店真实菜单，剔除辣品；
3. 在 35 元内枚举「主食+小食+饮料」组合并排序；
4. 对 Top3 调 `query-store-coupons` + `calculate-price` 核出真实到手价；
5. 输出三方案对比与推荐结论。

## 六、文件结构

```
mcd-combo-saver/
├── SKILL.md                    # WorkBuddy Skill 定义（核心）
├── mcd_combo_saver.py          # 参考命令行实现（含 mock 与真实 MCP 客户端）
├── README.md                   # 本文件
├── CONTEST_DECLARATION.md      # 参赛声明（官方要求，不可修改）
├── MCP_INTEGRATION.md          # MCP 集成说明
├── mcp-config.example.json     # 脱敏 MCP 配置（仅环境变量占位符）
├── workbuddy.md                # WorkBuddy 开发上下文（专项奖励核验）
├── requirements.txt
└── .env.example
```

## 七、免责声明

本项目为麦当劳程序员节创意开发大赛参赛作品，由参赛者独立开发，**非麦当劳官方产品**。餐品信息、价格、供应与优惠状态以麦当劳官方渠道实时结果为准；输出仅供参考，不构成任何专业建议。使用需遵守《麦当劳 MCP 服务规则》。
