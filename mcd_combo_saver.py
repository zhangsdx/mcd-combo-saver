#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦门省钱组合器 (McD Combo Saver) —— 麦当劳预算约束餐品组合优化 · 参考命令行实现

真实运行需要麦当劳 MCP Token（环境变量 MCD_MCP_TOKEN，或通过 WorkBuddy 的 mcd-mcp 连接器）。
无 Token 时可用 --mock 模式运行演示（内置样例菜单，不访问官方接口）。

用法:
  # 演示（无需 Token）
  python mcd_combo_saver.py --mock --budget 40 --people 1
  python mcd_combo_saver.py --mock --budget 80 --people 2 --no-spicy

  # 真实模式（需 MCD_MCP_TOKEN，默认深圳）
  python mcd_combo_saver.py --budget 40 --people 1
  python mcd_combo_saver.py --budget 80 --people 2 --no-spicy --city 深圳
"""
import os
import sys
import json
import argparse

import urllib.request
import urllib.error

MCP_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2024-11-05"

# ---------------------------------------------------------------------------
# 关键词（真实菜单无显式“辣/饮料”字段，基于名称 + 分类 + 标签启发式判定）
# ---------------------------------------------------------------------------
SPICY_KW = ["辣", "麻辣", "香辣", "辣椒", "火辣", "川辣", "酸辣"]
DRINK_KW = ["可乐", "雪碧", "橙汁", "果汁", "咖啡", "茶", "奶", "汽水", "柠檬",
            "美年达", "芬达", "椰", "豆浆", "苏打", "水", "冰红", "拿铁", "奶绿",
            "麦炫酷", "美汁源", "纯牛奶", "燕麦奶", "饮", "汁", "酷"]
COMBO_NM = ["套餐", "件套", "分享餐", "单人餐", "双人", "多人餐", "拼盘"]

# ---------------------------------------------------------------------------
# Mock 样例菜单（近似值，仅用于无 Token 时演示算法；真实数据来自 query-meals）
# ---------------------------------------------------------------------------
MOCK_MENU = [
    {"code": "M01", "name": "麦辣鸡腿汉堡", "cat": "主食", "price": 21.0, "tags": ["辣"]},
    {"code": "M02", "name": "板烧鸡腿堡",   "cat": "主食", "price": 22.0, "tags": []},
    {"code": "M03", "name": "双层吉士汉堡", "cat": "主食", "price": 23.0, "tags": []},
    {"code": "M04", "name": "巨无霸",       "cat": "主食", "price": 24.0, "tags": []},
    {"code": "M05", "name": "吉士汉堡",     "cat": "主食", "price": 14.0, "tags": []},
    {"code": "M06", "name": "麦香鸡",       "cat": "主食", "price": 14.0, "tags": []},
    {"code": "M07", "name": "鳕鱼堡",       "cat": "主食", "price": 22.0, "tags": []},
    {"code": "S01", "name": "中薯条",       "cat": "小食", "price": 12.0, "tags": []},
    {"code": "S02", "name": "麦辣鸡翅(2块)", "cat": "小食", "price": 13.0, "tags": ["辣"]},
    {"code": "S03", "name": "麦乐鸡(5块)",  "cat": "小食", "price": 13.0, "tags": []},
    {"code": "S04", "name": "玉米杯",       "cat": "小食", "price": 9.0,  "tags": []},
    {"code": "S05", "name": "苹果片",       "cat": "小食", "price": 7.0,  "tags": []},
    {"code": "D01", "name": "可口可乐(中)", "cat": "饮料", "price": 10.0, "tags": []},
    {"code": "D02", "name": "雪碧(中)",     "cat": "饮料", "price": 10.0, "tags": []},
    {"code": "D03", "name": "蜜桃红茶(中)", "cat": "饮料", "price": 11.0, "tags": []},
    {"code": "D04", "name": "美禄(中)",     "cat": "饮料", "price": 12.0, "tags": []},
    {"code": "C01", "name": "巨无霸套餐(中薯+中可)",   "cat": "套餐", "price": 42.0, "tags": []},
    {"code": "C02", "name": "麦辣鸡腿堡套餐(中薯+中可)", "cat": "套餐", "price": 39.0, "tags": ["辣"]},
    {"code": "C03", "name": "双层吉士套餐(中薯+中可)",   "cat": "套餐", "price": 41.0, "tags": []},
    {"code": "C04", "name": "板烧鸡腿堡套餐(中薯+中可)", "cat": "套餐", "price": 43.0, "tags": []},
    {"code": "T01", "name": "圆筒冰淇淋", "cat": "甜品", "price": 6.0,  "tags": []},
    {"code": "T02", "name": "麦旋风(OREO)", "cat": "甜品", "price": 12.0, "tags": []},
]

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


def _combo_meta(combo, nutrition):
    price = round(sum(x["price"] for x in combo), 2)
    cats = set(x["cat"] for x in combo)
    kcal = sum(nutrition.get(x["code"], {}).get("kcal", 0) for x in combo)
    protein = sum(nutrition.get(x["code"], {}).get("protein", 0) for x in combo)
    return price, cats, kcal, protein


def recommend(menu, budget, people, spicy_ok, must_drink, nutrition=None):
    nutrition = nutrition or {}
    all_combos = build_combos(menu, budget, spicy_ok, must_drink)

    def score(combo):
        _, cats, _, _ = _combo_meta(combo, nutrition)
        items = len(combo)
        price = sum(x["price"] for x in combo)
        return (items * 1.0 + len(cats) * 0.8) / price

    def _has(combo, cat):
        return any(x["cat"] == cat for x in combo)

    # A 极致省钱：非套餐、含主食+饮料的达标组合里，价格最低（花最少的钱吃一顿正经饭）
    达标_pool = [c for c in all_combos
                 if not _has(c, "套餐") and _has(c, "主食") and _has(c, "饮料")]
    达标_pool.sort(key=lambda c: sum(x["price"] for x in c))
    # B 套餐省事：优先「真套餐」（名称含 套餐/件套/分享餐），没有再退回任意带套餐标签的组合；取最便宜
    combo_all = [c for c in all_combos if _has(c, "套餐")]
    combo_real = [c for c in combo_all
                  if any(("套餐" in i["name"] or "件套" in i["name"] or "分享餐" in i["name"]) for i in c)]
    combo_pool = combo_real or combo_all
    combo_pool.sort(key=lambda c: sum(x["price"] for x in c))
    # C 吃饱实惠：不含套餐/甜品、含主食+饮料，价格最高（最丰盛、最接近预算）
    hearty_pool = [c for c in all_combos
                   if not _has(c, "套餐") and not _has(c, "甜品")
                   and _has(c, "主食") and _has(c, "饮料")]
    hearty_pool.sort(key=lambda c: sum(x["price"] for x in c), reverse=True)

    picks, labels = [], []
    if 达标_pool:
        picks.append(达标_pool[0]); labels.append("极致省钱")
    if combo_pool:
        picks.append(combo_pool[0]); labels.append("套餐省事")
    if hearty_pool:
        picks.append(hearty_pool[0]); labels.append("吃饱实惠")

    seen, results = set(), []
    for combo, label in zip(picks, labels):
        key = tuple(sorted(x["code"] for x in combo))
        if key in seen:
            continue
        seen.add(key)
        price, cats, kcal, protein = _combo_meta(combo, nutrition)
        results.append({
            "rank": len(results) + 1,
            "label": label,
            "items": [{"name": x["name"], "price": x["price"], "cat": x["cat"], "code": x["code"]} for x in combo],
            "subtotal": price,
            "payable": price,
            "coupon": None,
            "savings": round(budget - price, 2),
            "categories": sorted(cats),
            "kcal": kcal,
            "protein": protein,
        })
    return results


def render(results, total_budget, people, spicy_ok, must_drink, real=False):
    per_cap = total_budget / people
    print("=" * 60)
    print(f"麦门省钱组合器 · 总预算 ¥{total_budget} · {people} 人 · 人均上限 ¥{per_cap:.1f} · "
          f"{'不辣' if not spicy_ok else '可辣'} · {'必含饮料' if must_drink else '可无饮料'}")
    if real:
        print("数据源: 麦当劳 MCP 实时拉取（query-nearby-stores / query-meals / calculate-price）")
    print("=" * 60)
    for r in results:
        total = r["payable"] * people
        total_save = total_budget - total
        coupon_txt = f" ｜ 优惠 -¥{r['coupon']}" if r.get("coupon") else ""
        print(f"\n方案 {r['rank']}【{r['label']}】｜ 人均到手 ¥{r['payable']}（菜单小计 ¥{r['subtotal']}）{coupon_txt}"
              f" ｜ 人均结余 ¥{r['savings']}")
        for it in r["items"]:
            print(f"   - {it['name']:<18} ¥{it['price']}  [{it['cat']}]")
        nut = f"  营养: ~{r['kcal']} kcal / {r['protein']}g 蛋白" if r['kcal'] else ""
        print(f"  品类覆盖: {','.join(r['categories'])}{nut}")
        print(f"  ×{people} 人整单约 ¥{total:.1f}（外送可能含配送费），整单结余 ¥{total_save:.1f}")
    if results:
        best = results[0]
        print("\n" + "-" * 60)
        print(f"结论: 最推荐【方案 {best['rank']}·{best['label']}】，"
              f"{'、'.join(i['name'] for i in best['items'])}，人均到手约 ¥{best['payable']}。")
        if len(results) > 1:
            alt = results[1]
            print(f"想更省事可选【方案 {alt['rank']}·{alt['label']}】；想更管饱可选其余方案。")
        if not real:
            print("（mock 演示价；真实到手价请以 calculate-price 核价结果为准）")
    print("-" * 60)


# ---------------------------------------------------------------------------
# 真实 MCP 客户端（Streamable HTTP）—— 需在 WorkBuddy 连接器或本 CLI 配 Token
# ---------------------------------------------------------------------------
def _sc(resp):
    try:
        return resp["result"]["structuredContent"]
    except Exception:
        return None


class McdMCP:
    def __init__(self, token):
        self.token = token
        self.rid = 0
        self.sid = None

    def _post(self, payload):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(MCP_URL, data=data, method="POST")
        req.add_header("Authorization", "Bearer " + self.token)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        if self.sid:
            req.add_header("Mcp-Session-Id", self.sid)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode("utf-8", "replace")
                if "Mcp-Session-Id" in r.headers:
                    self.sid = r.headers["Mcp-Session-Id"]
                ct = r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            ct = e.headers.get("Content-Type", "")
        return raw, ct

    def _rpc(self, method, params=None):
        self.rid += 1
        payload = {"jsonrpc": "2.0", "id": self.rid, "method": method}
        if params is not None:
            payload["params"] = params
        raw, ct = self._post(payload)
        if "text/event-stream" in ct:
            chunks = []
            for line in raw.splitlines():
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
            return json.loads(raw)
        except Exception:
            return {}

    def initialize(self):
        self._rpc("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "mcd-combo-saver", "version": "1.0.0"},
        })
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call(self, name, args):
        return self._rpc("tools/call", {"name": name, "arguments": args})


# ---------------------------------------------------------------------------
# 真实数据解析（依据麦当劳 MCP 返回的 structuredContent 结构）
# ---------------------------------------------------------------------------
def _classify(name, cat_name, tags):
    name = name or ""
    cat_name = cat_name or ""
    # 酱料/蘸料类（非正餐）不参与组合
    if ("酱" in name or "蘸" in name) and not any(w in name for w in ["鸡", "堡", "肉", "鱼", "虾", "排", "卷"]):
        return "其他"
    if "套餐" in (tags or []):
        return "套餐"
    if any(k in name for k in COMBO_NM) or "餐" in cat_name or "拼盘" in cat_name:
        return "套餐"
    if "饮品" in cat_name or "麦咖啡" in cat_name:
        return "饮料"
    if any(k in name for k in DRINK_KW):
        return "饮料"
    if "小食" in cat_name or "甜品" in cat_name:
        return "小食"
    if any(k in name for k in ["冰淇淋", "麦旋风", "圣代", "薯", "鸡块", "鸡翅",
                                "鸡排", "派", "扭扭", "玉米", "炸鸡"]):
        return "小食"
    return "主食"


def _is_spicy(name, tags):
    blob = (name or "") + " " + " ".join(tags or [])
    return any(k in blob for k in SPICY_KW)


def _first_store_code(resp):
    try:
        data = _sc(resp)
        if isinstance(data, dict):
            lst = data.get("data", data)
        else:
            lst = data
        if isinstance(lst, list) and lst:
            for it in lst:
                if isinstance(it, dict) and it.get("storeCode"):
                    return it["storeCode"]
    except Exception:
        return None
    return None


def _parse_meals(resp):
    try:
        sc = _sc(resp)
        data = sc.get("data", {}) if isinstance(sc, dict) else {}
        cats = data.get("categories", [])
        meals = data.get("meals", {})
        code_tags, code_cat = {}, {}
        for c in cats:
            cn = c.get("name", "")
            for m in c.get("meals", []):
                code = m.get("code")
                if code:
                    code_tags.setdefault(code, []).extend(m.get("tags", []))
                    code_cat.setdefault(code, cn)
        out = []
        for code, m in meals.items():
            name = m.get("name", "")
            try:
                price = float(m.get("currentPrice") or m.get("originalPrice") or 0)
            except Exception:
                price = 0.0
            tags = list(code_tags.get(code, []))
            cat = _classify(name, code_cat.get(code, ""), tags)
            if _is_spicy(name, tags) and "辣" not in tags:
                tags.append("辣")
            out.append({"code": code, "name": name, "cat": cat, "price": price, "tags": tags})
        return out
    except Exception as e:
        print(f"[警告] 解析真实菜单失败：{e}")
        return []


def fetch_real_menu(token, city, keyword="", search_type=2, be_type=1, store_code=None):
    """调用真实 MCP 拉取门店与菜单，返回 (menu, store_code, mcp)。失败抛错。"""
    mcp = McdMCP(token)
    mcp.initialize()
    if not store_code:
        stores = mcp.call("query-nearby-stores",
                          {"beType": be_type, "searchType": search_type, "city": city, "keyword": keyword})
        store_code = _first_store_code(stores)
    if not store_code:
        raise RuntimeError("未从 query-nearby-stores 获取到门店编码")
    meals = mcp.call("query-meals", {"storeCode": store_code, "orderType": 1, "beType": 1})
    menu = _parse_meals(meals)
    return menu, store_code, mcp


def price_combo(mcp, store_code, combo):
    """调 calculate-price 核价，返回 (payable元, discount元) 或 None。
    注：麦当劳 calculate-price 返回的金额单位为「分」。"""
    items = [{"productCode": x["code"], "quantity": 1} for x in combo]
    resp = mcp.call("calculate-price",
                    {"storeCode": store_code, "orderType": 1, "beType": 1,
                     "items": items, "needTableware": False})
    sc = _sc(resp)
    if not sc:
        return None
    data = sc.get("data", {})
    if not isinstance(data, dict):
        return None
    payable = data.get("price")          # 应付现价（分）
    discount = data.get("discount", 0)   # 优惠金额（分）
    if payable is None:
        return None
    return float(payable) / 100.0, float(discount or 0) / 100.0


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="麦门省钱组合器")
    ap.add_argument("--mock", action="store_true", help="使用内置样例菜单（无需 Token）")
    ap.add_argument("--budget", type=float, required=True, help="预算上限（元，整单总额）")
    ap.add_argument("--people", type=int, default=1, help="用餐人数")
    ap.add_argument("--no-spicy", action="store_true", help="不接受辣")
    ap.add_argument("--no-drink", action="store_true", help="不必含饮料")
    ap.add_argument("--city", default="深圳", help="定位城市（真实模式）")
    ap.add_argument("--keyword", default="", help="位置关键词，如 福田（真实模式）")
    ap.add_argument("--store", default="", help="指定门店编码，跳过门店搜索（真实模式）")
    args = ap.parse_args()

    spicy_ok = not args.no_spicy
    must_drink = not args.no_drink
    per_cap = args.budget / args.people

    menu, store_code, mcp = MOCK_MENU, None, None
    real = False
    if args.mock:
        print("[提示] mock 演示模式。\n")
    elif os.environ.get("MCD_MCP_TOKEN"):
        try:
            menu, store_code, mcp = fetch_real_menu(
                os.environ["MCD_MCP_TOKEN"], args.city, args.keyword, store_code=args.store or None)
            if not menu:
                print("[警告] 真实菜单解析为空，降级为 mock 演示。\n")
            else:
                real = True
                print(f"[真实模式] 门店 {store_code} · 拉取 {len(menu)} 个餐品。\n")
        except Exception as e:
            print(f"[警告] 真实 MCP 调用失败（{e}），降级为 mock 演示。\n")
    else:
        print("[提示] 未检测到 MCD_MCP_TOKEN，自动使用 mock 演示模式。\n")

    results = recommend(menu, per_cap, args.people, spicy_ok, must_drink)
    if real and mcp and store_code:
        for r in results:
            p = price_combo(mcp, store_code, [{"code": i["code"]} for i in r["items"]])
            if p:
                payable, discount = p
                r["payable"] = round(payable, 2)
                r["coupon"] = round(discount, 2) if discount else None
                r["savings"] = round(per_cap - payable, 2)
    render(results, args.budget, args.people, spicy_ok, must_drink, real=real)


if __name__ == "__main__":
    main()
