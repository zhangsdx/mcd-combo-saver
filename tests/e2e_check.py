# -*- coding: utf-8 -*-
"""端到端回归：真实 MCP 拉数 + 分类断言 + 组合合法性 + 核价一致性（双门店）

用法：
    export MCD_MCP_TOKEN=<你的麦当劳 MCP Token>
    python tests/e2e_check.py

校验项：
  A. 分类：28 条人工核对过的品项，判定必须与预期一致
  B. 组合：不超预算 / 无重复 / 不辣约束 / 必含饮料 / 不含周边甜品限购品 / 有主食
  C. 核价：每个方案真调 calculate-price，核价必须等于菜单小计（该门店无券时）
  D. 排序：方案按到手价单调递增
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import mcd_combo_saver as M

TOKEN = os.environ.get("MCD_MCP_TOKEN")
if not TOKEN:
    sys.exit("请先设置环境变量 MCD_MCP_TOKEN（麦当劳 MCP 的 Bearer Token）")
# (显示名, city, keyword)  —— 福田店 96 项 / 深圳北站店 83 项，价格不同
STORES = [("福田(1420450)", "深圳", "福田"), ("深圳北站(1420227)", "深圳", "深圳")]

# 已人工核对的分类断言（两店合并）
ASSERT = {
    # 福田店
    "521956": "其他",  # 麦当劳限定丝巾
    "1401": "小食",    # 麦乐鸡
    "9900008752": "甜品",  # 派
    "521951": "甜品",  # 灰焰圆筒
    "9900015726": "小食",  # 韩式甜辣酱鸡块8块
    "9900015730": "小食",  # BFF四宫格小食盘
    "9900015729": "小食",  # 蘸酱BFF四宫格小食盘
    "9900013304": "套餐",  # 人气经典随心配
    "9900015568": "套餐",  # 精选超值随心配
    "9900016057": "套餐",  # 汉堡开心乐园餐
    "9900016058": "套餐",  # 鱼排堡开心乐园餐
    "9900003538": "饮料",  # 学生专享饮品随心选
    "9900003537": "套餐",  # 学生专享汉堡小食随心选
    "521797": "其他",  # 北美招牌牧场酱
    "521799": "其他",  # 日式鲜磨山葵酱
    "511781": "主食",  # 培根安格斯厚牛堡
    "4648": "主食",    # 不素之霸双层牛堡
    # 深圳北站店专属
    "9900016078": "小食",  # 蘸酱麦麦脆汁鸡
    "9900005432": "小食",  # 麦麦脆汁鸡1块
    "9900003064": "套餐",  # 麦辣小食餐
    "9900003062": "套餐",  # 板烧小食餐
    "9900005421": "套餐",  # 鱼排堡开心乐园餐
    "9900005422": "套餐",  # 汉堡开心乐园餐
    "9900004066": "套餐",  # 堡堡随心拼（7件任选）
    "9900016055": "套餐",  # 开心亲子双人餐
    "515946": "饮料",      # 浓浓黑巧（冰/热）
    "3757": "饮料",        # 纯悦
    "2430": "饮料",        # 黄金橙橙
}

BUDGETS = [(35, 1, True, True), (40, 1, False, True), (60, 1, True, True),
           (80, 2, True, True), (100, 2, False, True), (45, 1, True, False)]

problems = []
summary = []

for label, city, kw in STORES:
    print("\n" + "#" * 82)
    print(f"# 门店 {label}")
    print("#" * 82)
    menu, store, mcp = M.fetch_real_menu(TOKEN, city, kw)
    dist = dict(Counter(m["cat"] for m in menu))
    print(f"餐品 {len(menu)} | 门店码 {store} | 分布 {dist}")

    # 分类断言
    miss = 0
    for code, exp in ASSERT.items():
        it = next((m for m in menu if m["code"] == code), None)
        if not it:
            continue
        if it["cat"] != exp:
            problems.append(f"[{label}] 分类错判 {code} {it['name']}: {it['cat']} != {exp}")
            print(f"  ✗ {code} {it['name']} 判定{it['cat']} 期望{exp}")
            miss += 1
    print(f"  分类断言: {len(ASSERT)} 项 / 命中 {len([c for c in ASSERT if any(m['code']==c for m in menu)])} 项 / 失败 {miss}")

    # 一致性：主食里不该出现「餐/套/酱/丝巾」
    for m in menu:
        if m["cat"] == "主食" and (m["name"].endswith("餐") or "套餐" in m["name"]
                                  or "丝巾" in m["name"] or "酱" in m["name"]):
            problems.append(f"[{label}] 主食含异常项 {m['name']}")

    # 组合 + 核价
    for budget, people, spicy_ok, must_drink in BUDGETS:
        per = budget / people
        res = M.recommend(menu, per, people, spicy_ok, must_drink)
        tag = f"{label} ¥{budget}/{people}人 {'可辣' if spicy_ok else '不辣'} {'必含饮' if must_drink else '可无饮'}"
        print(f"\n  >>> {tag} -> {len(res)} 方案")
        # 方案之间不得重复；价格必须单调不减（否则 rank 顺序会误导）
        keys = [tuple(sorted(i["code"] for i in x["items"])) for x in res]
        if len(keys) != len(set(keys)):
            problems.append(f"{tag} 方案内容重复")
        prices = [x["payable"] for x in res]
        if prices != sorted(prices):
            problems.append(f"{tag} 方案价格非单调递增: {prices}")
        for r in res:
            codes = [i["code"] for i in r["items"]]
            srcs = [next((m for m in menu if m["code"] == c), None) for c in codes]
            is_sm = "套餐" in r["categories"]
            if len(codes) != len(set(codes)):
                problems.append(f"{tag} 方案{r['rank']} 商品重复")
            if r["subtotal"] > per + 0.01:
                problems.append(f"{tag} 方案{r['rank']} 超预算 {r['subtotal']}>{per}")
            if not spicy_ok:
                for s in srcs:
                    if s and "辣" in s["tags"]:
                        problems.append(f"{tag} 方案{r['rank']} 含辣 {s['name']}")
            if must_drink and not is_sm and "饮料" not in r["categories"]:
                problems.append(f"{tag} 方案{r['rank']} 缺饮料")
            if not must_drink and not is_sm and "饮料" in r["categories"]:
                problems.append(f"{tag} 方案{r['rank']} 指定不必含饮却含饮")
            for s in srcs:
                if s and s["cat"] in ("其他", "甜品"):
                    problems.append(f"{tag} 方案{r['rank']} 含非餐品 {s['name']}")
                if s and s.get("restricted"):
                    problems.append(f"{tag} 方案{r['rank']} 含限购品 {s['name']}")
            if not is_sm and "主食" not in r["categories"]:
                problems.append(f"{tag} 方案{r['rank']} 无主食")
            p = M.price_combo(mcp, store, [{"code": c} for c in codes])
            if not p:
                problems.append(f"{tag} 方案{r['rank']} 核价失败")
                calc = "核价失败"
            else:
                calc = f"¥{p[0]}"
                if abs(p[0] - r["subtotal"]) > 0.01:
                    problems.append(f"{tag} 方案{r['rank']} 核价≠小计 {p[0]} vs {r['subtotal']}")
                    calc += " ≠小计!"
            print(f"     {r['rank']}.【{r['label']}】小计¥{r['subtotal']:<6} 核价{calc:<10} "
                  + " + ".join(f"{i['name']}(¥{i['price']})" for i in r["items"]))
    summary.append((label, len(menu), dist))

print("\n" + "=" * 82)
print("【问题汇总】")
print("=" * 82)
if problems:
    for i, p in enumerate(problems, 1):
        print(f"  [{i}] {p}")
else:
    print("  ✓ 两门店全部校验通过：分类无错判、核价无差异、搭配无违规")
