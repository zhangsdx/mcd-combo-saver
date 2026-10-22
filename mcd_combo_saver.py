#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦门省钱组合器 (McD Combo Saver) —— 麦当劳预算约束餐品组合优化 · 参考命令行实现

真实运行需要麦当劳 MCP Token（环境变量 MCD_MCP_TOKEN）。
无 Token 时可用 --mock 模式运行演示（内置样例菜单，不访问官方接口）。

用法:
  # 演示（无需 Token）
  python mcd_combo_saver.py --mock --budget 40 --people 1
  python mcd_combo_saver.py --mock --budget 80 --people 2 --no-spicy

  # 真实模式（需 MCD_MCP_TOKEN）
  python mcd_combo_saver.py --budget 40 --people 1 --city 深圳
"""
import os
import sys
import json
import argparse
from itertools import product

try:
    import requests
except ImportError:
    requests = None

MCP_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2024-11-05"

# ---------------------------------------------------------------------------
# Mock 样例菜单（近似值，仅用于无 Token 时演示算法；真实数据来自 query-meals）
# ---------------------------------------------------------------------------
MOCK_MENU = [
    # 主食
    {"code": "M01", "name": "麦辣鸡腿汉堡", "cat": "主食", "price": 21.0, "tags": ["辣"]},
    {"code": "M02", "name": "板烧鸡腿堡",   "cat": "主食", "price": 22.0, "tags": []},
    {"code": "M03", "name": "双层吉士汉堡", "cat": "主食", "price": 23.0, "tags": []},
    {"code": "M04", "name": "巨无霸",       "cat": "主食", "price": 24.0, "tags": []},
    {"code": "M05", "name": "吉士汉堡",     "cat": "主食", "price": 14.0, "tags": []},
    {"code": "M06", "name": "麦香鸡",       "cat": "主食", "price": 14.0, "tags": []},
    {"code": "M07", "name": "鳕鱼堡",       "cat": "主食", "price": 22.0, "tags": []},
    # 小食
    {"code": "S01", "name": "中薯条",       "cat": "小食", "price": 12.0, "tags": []},
    {"code": "S02", "name": "麦辣鸡翅(2块)", "cat": "小食", "price": 13.0, "tags": ["辣"]},
    {"code": "S03", "name": "麦乐鸡(5块)",  "cat": "小食", "price": 13.0, "tags": []},
    {"code": "S04", "name": "玉米杯",       "cat": "小食", "price": 9.0,  "tags": []},
    {"code": "S05", "name": "苹果片",       "cat": "小食", "price": 7.0,  "tags": []},
    # 饮料
    {"code": "D01", "name": "可口可乐(中)", "cat": "饮料", "price": 10.0, "tags": []},
    {"code": "D02", "name": "雪碧(中)",     "cat": "饮料", "price": 10.0, "tags": []},
    {"code": "D03", "name": "蜜桃红茶(中)", "cat": "饮料", "price": 11.0, "tags": []},
    {"code": "D04", "name": "美禄(中)",     "cat": "饮料", "price": 12.0, "tags": []},
    # 套餐（已含 主食+小食+饮料）
    {"code": "C01", "name": "巨无霸套餐(中薯+中可)",   "cat": "套餐", "price": 42.0, "tags": []},
    {"code": "C02", "name": "麦辣鸡腿堡套餐(中薯+中可)", "cat": "套餐", "price": 39.0, "tags": ["辣"]},
    {"code": "C03", "name": "双层吉士套餐(中薯+中可)",   "cat": "套餐", "price": 41.0, "tags": []},
    {"code": "C04", "name": "板烧鸡腿堡套餐(中薯+中可)", "cat": "套餐", "price": 43.0, "tags": []},
    # 甜品
    {"code": "T01", "name": "圆筒冰淇淋", "cat": "甜品", "price": 6.0,  "tags": []},
    {"code": "T02", "name": "麦旋风(OREO)", "cat": "甜品", "price": 12.0, "tags": []},
]

# 样例营养（部分，仅 mock；真实来自 list-nutrition-foods）
MOCK_NUTRITION = {
    "M01": {"kcal": 498, "protein": 19}, "M04": {"kcal": 504, "protein": 26},
    "M03": {"kcal": 440, "protein": 25}, "S01": {"kcal": 320, "protein": 4},
    "D01": {"kcal": 147, "protein": 0},  "C01": {"kcal": 971, "protein": 30},
}


# ---------------------------------------------------------------------------
# 组合优化核心算法（与是否联网无关，纯逻辑，可单测）
# ---------------------------------------------------------------------------
def build_combos(menu, budget, spicy_ok, must_drink):
    allowed = [m for m in menu if (spicy_ok or "辣" not in m["tags"])]
    mains = [m for m in allowed if m["cat"] == "主食"]
    sides = [m for m in allowed if m["cat"] == "小食"]
    drinks = [m for m in allowed if m["cat"] == "饮料"]
    combos_cat = [m for m in allowed if m["cat"] == "套餐"]
    desserts = [m for m in allowed if m["cat"] == "甜品"]

    combos = []
    for c in combos_cat:                      # 套餐
        if c["price"] <= budget:
            combos.append([c])
    for m in mains:                           # 主食 + 饮料
        for d in drinks:
            if m["price"] + d["price"] <= budget:
                combos.append([m, d])
    for m in mains:                           # 主食 + 小食 + 饮料
        for s in sides:
            for d in drinks:
                if m["price"] + s["price"] + d["price"] <= budget:
                    combos.append([m, s, d])
    if not must_drink:                        # 主食 + 小食（无饮料）
        for m in mains:
            for s in sides:
                if m["price"] + s["price"] <= budget:
                    combos.append([m, s])
    # 允许用结余加一份甜品（升级版）
    extended = []
    for combo in combos:
        extended.append(combo)
        base = sum(x["price"] for x in combo)
        for de in desserts:
            if base + de["price"] <= budget:
                extended.append(combo + [de])
    combos = extended

    def score(combo):
        cats = set(x["cat"] for x in combo)
        items = len(combo)
        price = sum(x["price"] for x in combo)
        coverage = len(cats)
        # 价值 = (单品数 + 0.8*品类覆盖) / 单价；越丰盛越便宜越高分
        return (items * 1.0 + coverage * 0.8) / price

    combos.sort(key=lambda c: (score(c), -sum(x["price"] for x in c)), reverse=True)

    seen, uniq = set(), []
    for c in combos:
        key = tuple(sorted(x["code"] for x in c))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)
    return uniq


def _combo_meta(combo):
    price = round(sum(x["price"] for x in combo), 2)
    cats = set(x["cat"] for x in combo)
    kcal = sum(MOCK_NUTRITION.get(x["code"], {}).get("kcal", 0) for x in combo)
    protein = sum(MOCK_NUTRITION.get(x["code"], {}).get("protein", 0) for x in combo)
    has_combo = any(x["cat"] == "套餐" for x in combo)
    has_dessert = any(x["cat"] == "甜品" for x in combo)
    main = next((x for x in combo if x["cat"] == "主食"), None)
    return price, cats, kcal, protein, has_combo, has_dessert, main


def recommend(menu, budget, people, spicy_ok, must_drink):
    """输出三种不同策略的 Top 方案，保证实质差异：
       A 极致省钱（最划算填满）  B 套餐省事（单套餐）  C 吃饱实惠（主食+小食+饮料，量更足）
    """
    all_combos = build_combos(menu, budget, spicy_ok, must_drink)

    def score(combo):
        _, cats, _, _, _, _, _ = _combo_meta(combo)
        items = len(combo)
        price = sum(x["price"] for x in combo)
        return (items * 1.0 + len(cats) * 0.8) / price

    # 分池
    value_pool = sorted(all_combos, key=lambda c: (score(c), -sum(x["price"] for x in c)), reverse=True)
    combo_pool = [c for c in all_combos if any(x["cat"] == "套餐" for x in c)]
    combo_pool.sort(key=lambda c: sum(x["price"] for x in c), reverse=True)  # 量更足的套餐优先
    hearty_pool = [c for c in all_combos
                   if not any(x["cat"] == "套餐" for x in c)
                   and not any(x["cat"] == "甜品" for x in c)
                   and any(x["cat"] == "主食" for x in c)
                   and any(x["cat"] == "饮料" for x in c)]
    hearty_pool.sort(key=lambda c: sum(x["price"] for x in c), reverse=True)  # 更饱的优先

    picks = []
    labels = []
    # A 极致省钱
    if value_pool:
        picks.append(value_pool[0]); labels.append("极致省钱")
    # B 套餐省事
    if combo_pool:
        picks.append(combo_pool[0]); labels.append("套餐省事")
    # C 吃饱实惠
    if hearty_pool:
        picks.append(hearty_pool[0]); labels.append("吃饱实惠")

    # 去重（同餐品集合只留一个）
    seen, results = set(), []
    for combo, label in zip(picks, labels):
        key = tuple(sorted(x["code"] for x in combo))
        if key in seen:
            continue
        seen.add(key)
        price, cats, kcal, protein, _, _, _ = _combo_meta(combo)
        results.append({
            "rank": len(results) + 1,
            "label": label,
            "items": [{"name": x["name"], "price": x["price"], "cat": x["cat"]} for x in combo],
            "subtotal": price,
            "payable": price,          # mock：未叠加优惠券；真实由 calculate-price 覆盖
            "coupon": None,
            "savings": round(budget - price, 2),
            "categories": sorted(cats),
            "kcal": kcal,
            "protein": protein,
        })
    return results


def render(results, total_budget, people, spicy_ok, must_drink):
    per_cap = total_budget / people
    print("=" * 56)
    print(f"麦门省钱组合器 · 总预算 ¥{total_budget} · {people} 人 · 人均上限 ¥{per_cap:.1f} · "
          f"{'不辣' if not spicy_ok else '可辣'} · {'必含饮料' if must_drink else '可无饮料'}")
    print("=" * 56)
    for r in results:
        total = r["payable"] * people
        total_save = total_budget - total
        print(f"\n方案 {r['rank']}【{r['label']}】｜ 人均 ¥{r['payable']}（菜单小计 ¥{r['subtotal']}）"
              f" ｜ 人均结余 ¥{r['savings']}")
        for it in r["items"]:
            print(f"   - {it['name']:<16} ¥{it['price']}  [{it['cat']}]")
        nut = f"  营养: ~{r['kcal']} kcal / {r['protein']}g 蛋白" if r['kcal'] else ""
        print(f"  品类覆盖: {','.join(r['categories'])}{nut}")
        print(f"  ×{people} 人整单约 ¥{total:.1f}（外送可能有配送费，以 calculate-price 为准），整单结余 ¥{total_save:.1f}")
    if results:
        best = results[0]
        print("\n" + "-" * 56)
        print(f"结论: 最推荐【方案 {best['rank']}·{best['label']}】，"
              f"{'、'.join(i['name'] for i in best['items'])}，"
              f"人均约 ¥{best['payable']}。")
        if len(results) > 1:
            alt = results[1]
            print(f"想更省事可选【方案 {alt['rank']}·{alt['label']}】；想更管饱可选其余方案。")
    print("-" * 56)
    print("（mock 演示价；真实到手价请以 calculate-price 核价结果为准）")


# ---------------------------------------------------------------------------
# 真实 MCP 客户端（Streamable HTTP）—— 需在 WorkBuddy 连接器或本 CLI 配 Token
# ---------------------------------------------------------------------------
class McdMCP:
    def __init__(self, token):
        if requests is None:
            raise RuntimeError("真实模式需要 requests 库：pip install requests")
        self.s = requests.Session()
        self.h = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self.rid = 0
        self.sid = None

    def _rpc(self, method, params=None):
        self.rid += 1
        payload = {"jsonrpc": "2.0", "id": self.rid, "method": method}
        if params is not None:
            payload["params"] = params
        h = dict(self.h)
        if self.sid:
            h["Mcp-Session-Id"] = self.sid
        r = self.s.post(MCP_URL, headers=h, json=payload, timeout=30)
        if "Mcp-Session-Id" in r.headers:
            self.sid = r.headers["Mcp-Session-Id"]
        ct = r.headers.get("Content-Type", "")
        if "text/event-stream" in ct:
            chunks = []
            for line in r.text.splitlines():
                if line.startswith("data:"):
                    chunk = line[5:].strip()
                    if chunk and chunk != "[DONE]":
                        chunks.append(chunk)
            for d in reversed(chunks):
                try:
                    obj = json.loads(d)
                    if obj.get("id") == self.rid:
                        return obj
                except Exception:
                    pass
            return json.loads(chunks[-1]) if chunks else {}
        try:
            return r.json()
        except Exception:
            return {}

    def initialize(self):
        self._rpc("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "mcd-combo-saver", "version": "1.0.0"},
        })
        h = dict(self.h)
        if self.sid:
            h["Mcp-Session-Id"] = self.sid
        self.s.post(MCP_URL, headers=h,
                    json={"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call(self, name, args):
        return self._rpc("tools/call", {"name": name, "arguments": args})


def fetch_real_menu(token, city):
    """调用真实 MCP 拉取菜单并转换为内部格式。失败时抛错，由上层降级提示。"""
    mcp = McdMCP(token)
    mcp.initialize()
    stores = mcp.call("query-nearby-stores", {"city": city})
    # 取第一个门店 code（真实场景应让用户确认）
    store_code = _first_store_code(stores)
    meals = mcp.call("query-meals", {"storeCode": store_code})
    return _parse_meals(meals), store_code


def _first_store_code(resp):
    try:
        return resp["result"]["content"][0]["text"]
    except Exception:
        return None


def _parse_meals(resp):
    # 依据 MCP 返回结构解析；结构随官方变化，这里做容错
    try:
        text = resp["result"]["content"][0]["text"]
        data = json.loads(text)
        out = []
        for it in data.get("meals", data if isinstance(data, list) else []):
            out.append({
                "code": it.get("code", it.get("id", "")),
                "name": it.get("name", ""),
                "cat": it.get("category", "主食"),
                "price": float(it.get("price", 0)),
                "tags": it.get("tags", []),
            })
        return out
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="麦门省钱组合器")
    ap.add_argument("--mock", action="store_true", help="使用内置样例菜单（无需 Token）")
    ap.add_argument("--budget", type=float, required=True, help="预算上限（元）")
    ap.add_argument("--people", type=int, default=1, help="用餐人数")
    ap.add_argument("--no-spicy", action="store_true", help="不接受辣")
    ap.add_argument("--no-drink", action="store_true", help="不必含饮料")
    ap.add_argument("--city", default="深圳", help="定位城市（真实模式）")
    args = ap.parse_args()

    spicy_ok = not args.no_spicy
    must_drink = not args.no_drink
    per_cap = args.budget / args.people  # 单人上限 = 总预算 / 人数

    if args.mock or not os.environ.get("MCD_MCP_TOKEN"):
        if not args.mock:
            print("[提示] 未检测到 MCD_MCP_TOKEN，自动使用 mock 演示模式。\n")
        menu = MOCK_MENU
    else:
        try:
            menu, _ = fetch_real_menu(os.environ["MCD_MCP_TOKEN"], args.city)
            if not menu:
                print("[警告] 真实菜单解析为空，降级为 mock 演示。\n")
                menu = MOCK_MENU
        except Exception as e:
            print(f"[警告] 真实 MCP 调用失败（{e}），降级为 mock 演示。\n")
            menu = MOCK_MENU

    results = recommend(menu, per_cap, args.people, spicy_ok, must_drink)
    render(results, args.budget, args.people, spicy_ok, must_drink)


if __name__ == "__main__":
    main()
