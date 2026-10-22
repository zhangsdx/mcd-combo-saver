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
#
# 经验值全部来自 2026-10-22 门店 1420450 的真实菜单（96 项 / 15 分类）核对。
# 注意：不要用「水 / 茶 / 奶 / 汁 / 酷」这类单字做饮料判定，会误伤
#      「水果」「奶茶味酱」等；真实菜单里所有饮品都能由分类名「饮品 / 麦咖啡」命中。
# ---------------------------------------------------------------------------
SPICY_KW = ["辣", "麻辣", "香辣", "辣椒", "火辣", "川辣", "酸辣", "龙焰", "甜辣"]
DRINK_KW = ["可乐", "雪碧", "芬达", "美年达", "咖啡", "拿铁", "奶铁", "红茶",
            "绿茶", "橙汁", "果汁", "苹果汁", "牛奶", "燕麦奶", "豆浆", "雪冰",
            "麦炫酷", "美汁源", "柠檬茶", "汽水", "矿泉水", "饮品", "怡泉"]
# 名称里的「强套餐词」——命中即视为整份套餐，不再按单品处理
COMBO_NM = ["套餐", "件套", "分享餐", "单人餐", "双人餐", "多人餐",
            "乐园餐", "随心配", "随心选", "随心拼", "拼盘"]
# 甜品类：必须与「小食」分开，否则会拿冰淇淋冒充正餐去凑“吃饱实惠”
DESSERT_KW = ["圆筒", "麦旋风", "圣代", "新地", "冰淇淋", "甜筒", "苹果派",
              "菠萝派", "香芋派", "红豆派"]
# 小食类（名称）
SNACK_KW = ["鸡块", "麦乐鸡", "鸡翅", "鸡排", "鸡米花", "鸡柳", "洋葱圈",
            "薯条", "薯", "玉米", "炸鸡", "脆汁鸡", "麦麦脆",
            "小食盘", "四宫格", "扭扭"]
# 周边 / 非餐品：真实菜单里混有「麦当劳限定丝巾」，绝不能进餐单
NONFOOD_KW = ["丝巾", "玩偶", "玩具", "徽章", "帆布袋", "周边", "礼品卡",
              "手提袋", "餐盒", "盲盒", "摆件"]
# 限购/身份限定商品：如「学生专享饮品随心选」需学生身份才能下单，
# 默认不参与推荐，否则会给出「买不到」的方案。
RESTRICTED_KW = ["学生专享"]

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
def build_combos(menu, budget, spicy_ok, must_drink, include_restricted=False):
    """枚举预算内所有合规组合。

    must_drink=True  ：只生成「含饮料」的组合（主食+饮料 / 主食+小食+饮料），
                      套餐本身含饮料，始终合法。
    must_drink=False ：只生成「不含饮料」的组合（单主食 / 主食+小食），
                      让 --no-drink 真正生效（旧版无论开关都会塞饮料组合）。
    include_restricted：是否允许「学生专享」这类需身份验证的商品加入。

    甜品不参与自动组合：旧版把甜品当「小食」并允许加在套餐后，
    导致「吃饱实惠」用 ¥5 圆筒冰淇淋凑预算，语义错误。
    """
    allowed = [m for m in menu
               if m.get("price", 0) > 0
               and (spicy_ok or "辣" not in m["tags"])
               and (include_restricted or not m.get("restricted"))]
    mains = [m for m in allowed if m["cat"] == "主食"]
    sides = [m for m in allowed if m["cat"] == "小食"]
    drinks = [m for m in allowed if m["cat"] == "饮料"]
    setmeals = [m for m in allowed if m["cat"] == "套餐"]

    combos = []
    for c in setmeals:                        # 套餐：自带主食+小食+饮料
        if c["price"] <= budget:
            combos.append([c])
    if must_drink:
        for m in mains:                       # 主食 + 饮料
            for d in drinks:
                if m["price"] + d["price"] <= budget:
                    combos.append([m, d])
        for m in mains:                       # 主食 + 小食 + 饮料
            for s in sides:
                for d in drinks:
                    if m["price"] + s["price"] + d["price"] <= budget:
                        combos.append([m, s, d])
    else:
        for m in mains:                       # 只有主食
            if m["price"] <= budget:
                combos.append([m])
        for m in mains:                       # 主食 + 小食
            for s in sides:
                if m["price"] + s["price"] <= budget:
                    combos.append([m, s])

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


# 标准「套餐」词——用于「套餐省事」策略。故意不含「随心配/随心选」：
# 那两个是 1+1 自选组合，跟三件套/四件套不是一类，混在一起会出现
# 「方案1 精选超值随心配 ¥13.9 / 方案2 人气经典随心配 ¥14.9」这种同质化推荐。
STRONG_SETMEAL_KW = ["套餐", "件套", "分享餐", "单人餐", "双人餐", "多人餐", "乐园餐"]


def _is_real_setmeal(name):
    """名称里带标准套餐词才算「真套餐」（排除 1+1 随心配、随心选这类自选组合）。"""
    return any(k in (name or "") for k in STRONG_SETMEAL_KW)


def recommend(menu, budget, people, spicy_ok, must_drink, nutrition=None,
              include_restricted=False):
    nutrition = nutrition or {}
    all_combos = build_combos(menu, budget, spicy_ok, must_drink, include_restricted)

    def _has(combo, cat):
        return any(x["cat"] == cat for x in combo)

    def _price(combo):
        return sum(x["price"] for x in combo)

    def _key(combo):
        return tuple(sorted(x["code"] for x in combo))

    def _ok(combo):
        """合规下限：不含甜品/周边；有主食（或整份套餐）；饮料按开关判断。"""
        if _has(combo, "甜品") or _has(combo, "其他"):
            return False
        if not (_has(combo, "主食") or _has(combo, "套餐")):
            return False
        if must_drink and not (_has(combo, "饮料") or _has(combo, "套餐")):
            return False
        return True

    def _coverage(combo):
        """品类覆盖数。套餐内部已含主食+小食+饮料，按 3 个品类计，
        否则一份三件套（只算"套餐"1 类）会输给「主食+小食」而被判为不够丰盛。"""
        cats = set()
        for x in combo:
            if x["cat"] == "套餐":
                cats.update(["主食", "小食", "饮料"])
            else:
                cats.add(x["cat"])
        return len(cats)

    ok_pool = [c for c in all_combos if _ok(c)]

    # A 极致省钱：**全场**（含套餐）价格最低——否则会出现「极致省钱 ¥23.5」
    #   比「套餐省事 ¥13.9」还贵的自相矛盾（旧版只在单点组合里找最低）
    cheapest = sorted(ok_pool, key=_price)
    # B 套餐省事：真套餐里最便宜（跳过与 A 重复的那一份）
    setmeals = sorted([c for c in all_combos
                       if _has(c, "套餐") and any(_is_real_setmeal(i["name"]) for i in c)],
                      key=_price)
    # C 吃饱实惠：品类覆盖优先（先保证有主食+小食+饮料），同覆盖下价格越高越贴预算，
    #   避免旧版出现「鳕鱼堡+纯牛奶」这种只有 2 个品类却叫“吃饱”的方案。
    #   排除套餐：套餐已有独立策略「套餐省事」，否则两个方案会撞成同一类。
    heartiest = sorted([c for c in ok_pool if not _has(c, "套餐")],
                       key=lambda c: (_coverage(c), _price(c)),
                       reverse=True)

    picks, labels, used = [], [], set()

    def _push(combo, label):
        k = _key(combo)
        if k in used:
            return False
        used.add(k)
        picks.append(combo)
        labels.append(label)
        return True

    if cheapest:
        _push(cheapest[0], "极致省钱")
    for c in setmeals:
        if _key(c) not in used:
            _push(c, "套餐省事")
            break
    for c in heartiest:
        if _key(c) not in used:
            _push(c, "吃饱实惠")
            break

    results = []
    for combo, label in zip(picks, labels):
        price, cats, kcal, protein = _combo_meta(combo, nutrition)
        results.append({
            "rank": 0,
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

    # 按价格升序重排并重编号：三个方案的标签是「策略名」不是「名次」，
    # 若不按价格排序会出现「方案2 ¥41」排在「方案3 ¥37」前面这种倒挂。
    results.sort(key=lambda r: (r["payable"], r["subtotal"]))
    for i, r in enumerate(results, 1):
        r["rank"] = i
    return results


def render(results, total_budget, people, spicy_ok, must_drink, real=False, coupon_count=0):
    per_cap = total_budget / people
    print("=" * 60)
    print(f"麦门省钱组合器 · 总预算 ¥{total_budget} · {people} 人 · 人均上限 ¥{per_cap:.1f} · "
          f"{'不辣' if not spicy_ok else '可辣'} · {'必含饮料' if must_drink else '可无饮料'}")
    if real:
        print("数据源: 麦当劳 MCP 实时拉取（query-nearby-stores / query-meals / calculate-price）")
        coupon_note = (f"该门店有 {coupon_count} 张券可选用（本工具不代领券，"
                       f"到手价为未叠券核价）" if coupon_count else "该门店当前无可用优惠券")
        print(f"计价口径: {coupon_note}")
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
        setmeal_note = "（套餐内已含小食与饮料）" if "套餐" in r["categories"] else ""
        print(f"  品类覆盖: {','.join(r['categories'])}{setmeal_note}{nut}")
        if any(("随心配" in it["name"] or "随心选" in it["name"]) for it in r["items"]):
            print("  注: 「随心配/随心选」需在门店选定具体商品，此处只锁定活动价档位。")
        print(f"  ×{people} 人整单约 ¥{total:.1f}（外送可能含配送费），整单结余 ¥{total_save:.1f}")
    if results:
        best = results[0]
        print("\n" + "-" * 60)
        print(f"结论: 最推荐【方案 {best['rank']}·{best['label']}】，"
              f"{'、'.join(i['name'] for i in best['items'])}，人均到手约 ¥{best['payable']}。")
        if len(results) > 1:
            others = "；".join(f"【方案 {r['rank']}·{r['label']}】¥{r['payable']}"
                              for r in results[1:])
            print(f"其它可选：{others}。")
        if not real:
            print("（mock 演示价；真实到手价请以 calculate-price 核价结果为准）")
    else:
        print(f"\n[无方案] 人均预算 ¥{per_cap:.1f} 不足以组成一餐"
              f"（{'需含饮料' if must_drink else '可不含饮料'}）。建议放宽预算、"
              f"或加 --no-drink 去掉饮料要求后重试。")
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
def _classify(name, cat_names, tags, price=0.0):
    """把真实菜单项归类为 套餐/主食/小食/饮料/甜品/其他。

    cat_names：该项出现的**全部**分类名（真实菜单里一件商品常同时挂在
    「人气热卖」和「小食甜品\\n/其他」下，只取第一个分类会判错，
    例如「麦当劳限定丝巾」会因首个分类是「人气热卖」而落入默认「主食」）。

    判定顺序（从强到弱，顺序本身就是业务规则）：
      周边 → 酱料 → 饮品类 → 名称套餐词 → 名称饮品词 → 名称甜品词
      → 名称小食词 → 分类兜底 → 默认主食
    """
    name = name or ""
    cats = [c for c in (cat_names or []) if c]
    blob = " ".join(cats)
    tags = tags or []

    # 1) 周边非餐品
    if any(k in name for k in NONFOOD_KW):
        return "其他"

    # 2) 酱料/蘸料（低价且名称以「酱」结尾，或标签就是「蘸酱」）
    #    注意不能只看「含酱字」——「蘸酱炸鸡」「蘸酱四宫格」是正经餐品
    if price <= 6 and (name.endswith("酱") or "蘸酱" in tags):
        return "其他"

    # 3) 饮品类（真实菜单里「饮品」「麦咖啡™」两个分类 100% 是饮料，
    #    必须先于套餐词判定，否则「学生专享饮品随心选」会被当成套餐）
    if "饮品" in blob or "麦咖啡" in blob:
        return "饮料"

    # 4) 名称含强套餐词（整份套餐，内部已含主食/小食/饮料）
    #    额外：名称以「餐」结尾也算套餐——真实菜单里「麦辣小食餐」「板烧小食餐」
    #    「汉堡开心乐园餐」「鱼排堡开心乐园餐」都以「餐」结尾，逐个加词不可维护。
    #    已核对：没有任何单品主食以「餐」结尾。
    if any(k in name for k in COMBO_NM) or name.endswith("餐"):
        return "套餐"

    # 5) 名称含饮品词
    if any(k in name for k in DRINK_KW):
        return "饮料"

    # 6) 名称含甜品词（必须早于小食词，否则圆筒/麦旋风会被当成小食）
    #    真实菜单里「派」的品名就叫单字「派」，故补 endswith 判断
    if any(k in name for k in DESSERT_KW) or name.endswith("派"):
        return "甜品"

    # 7) 名称含小食词
    if any(k in name for k in SNACK_KW):
        return "小食"

    # 8) 分类兜底（「炸鸡」分类下的都是小食，如「麦麦脆汁鸡1块」）
    if "小食" in blob or "甜品" in blob or "炸鸡" in blob:
        return "甜品" if ("甜品" in blob and "小食" not in blob and "炸鸡" not in blob) else "小食"
    if "单人餐" in blob or "多人餐" in blob or "套餐" in blob or "乐园" in blob:
        return "套餐"

    # 9) 默认：汉堡/卷/堡类
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
        code_tags, code_cats = {}, {}
        for c in cats:
            cn = (c.get("name") or "").strip()
            for m in c.get("meals", []):
                code = m.get("code")
                if code:
                    code_tags.setdefault(code, []).extend(m.get("tags", []))
                    bucket = code_cats.setdefault(code, [])
                    if cn and cn not in bucket:      # 收集全部分类名，不只第一个
                        bucket.append(cn)
        out = []
        for code, m in meals.items():
            name = m.get("name", "")
            try:
                price = float(m.get("currentPrice") or m.get("originalPrice") or 0)
            except Exception:
                price = 0.0
            if price <= 0:                            # 无价商品不参与组合，避免 0 元污染
                continue
            tags = list(code_tags.get(code, []))
            cat_names = code_cats.get(code, [])
            cat = _classify(name, cat_names, tags, price)
            if _is_spicy(name, tags) and "辣" not in tags:
                tags.append("辣")
            restricted = any(k in name for k in RESTRICTED_KW)
            out.append({"code": code, "name": name, "cat": cat, "price": price,
                        "tags": tags, "cats": cat_names, "restricted": restricted})
        return out
    except Exception as e:
        print(f"[警告] 解析真实菜单失败：{e}")
        return []


def fetch_real_menu(token, city, keyword="", search_type=2, be_type=1, store_code=None):
    """调用真实 MCP 拉取门店与菜单，返回 (menu, store_code, mcp)。失败抛错。

    实测（2026-10-22）：query-nearby-stores 在 searchType=2 时 keyword **不能为空**，
    传空字符串或无 keyword 一律返回空列表；把城市名当 keyword 才能命中。
    因此这里做三级回退：给定 keyword → 城市名 → 裸查。
    """
    mcp = McdMCP(token)
    mcp.initialize()
    if not store_code:
        tried, seen = [], []
        for kw in [keyword, city, ""]:
            if kw in seen:
                continue
            seen.append(kw)
            stores = mcp.call("query-nearby-stores",
                              {"beType": be_type, "searchType": search_type,
                               "city": city, "keyword": kw})
            store_code = _first_store_code(stores)
            tried.append(f"keyword={kw or '(空)'}")
            if store_code:
                break
        if not store_code:
            raise RuntimeError("未找到门店（已尝试 " + " / ".join(tried) +
                               "），请用 --keyword 指定位置，如 福田、南山")
    meals = mcp.call("query-meals", {"storeCode": store_code, "orderType": 1, "beType": 1})
    menu = _parse_meals(meals)
    return menu, store_code, mcp


def price_combo(mcp, store_code, combo, quantity=1):
    """调 calculate-price 核价，返回 (payable元, discount元) 或 None。

    注意：麦当劳 calculate-price 返回的金额单位是「分」，必须 /100。
    同一商品出现多次时按 quantity 合并，不重复下单行。
    """
    cnt = {}
    for x in combo:
        cnt[x["code"]] = cnt.get(x["code"], 0) + 1
    items = [{"productCode": c, "quantity": n * quantity} for c, n in cnt.items()]
    resp = mcp.call("calculate-price",
                    {"storeCode": store_code, "orderType": 1, "beType": 1,
                     "items": items, "needTableware": False})
    sc = _sc(resp)
    # 服务端失败时返回 {"success": false, "code": 60006, "message": "商品已售罄或不可售"}
    # 且不带 data 字段；必须显式判 success，否则可能把缺失字段当 0 元
    if not sc or sc.get("success") is False:
        return None
    data = sc.get("data", {})
    if not isinstance(data, dict):
        return None
    payable = data.get("price")          # 应付现价（分）
    discount = data.get("discount", 0)   # 优惠金额（分）
    if payable is None:
        return None
    return float(payable) / 100.0, float(discount or 0) / 100.0


def count_store_coupons(mcp, store_code):
    """返回该门店可用券数量；查询失败按 0 处理（不阻塞主流程）。"""
    try:
        resp = mcp.call("query-store-coupons",
                        {"storeCode": store_code, "beType": 1, "orderType": 1})
        sc = _sc(resp)
        if isinstance(sc, dict) and isinstance(sc.get("data"), list):
            return len(sc["data"])
    except Exception:
        pass
    return 0


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
    ap.add_argument("--student", action="store_true",
                    help="允许「学生专享」类需身份验证的商品参与推荐（默认排除）")
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

    results = recommend(menu, per_cap, args.people, spicy_ok, must_drink,
                        include_restricted=args.student)
    coupon_count = 0
    if real and mcp and store_code:
        coupon_count = count_store_coupons(mcp, store_code)
        for r in results:
            p = price_combo(mcp, store_code, [{"code": i["code"]} for i in r["items"]])
            if p:
                payable, discount = p
                r["payable"] = round(payable, 2)
                r["coupon"] = round(discount, 2) if discount else None
                r["savings"] = round(per_cap - payable, 2)
            else:
                # 核价失败必须留痕：不能让「菜单小计」冒充「真实到手价」
                r["priced"] = False
                print(f"[警告] 方案 {r['rank']}（{r['label']}）calculate-price 核价失败，"
                      f"展示值为菜单小计，仅供参考。\n")
        # 真核价可能带回优惠导致价格变化，按最终到手价重排一次
        results.sort(key=lambda r: (r["payable"], r["subtotal"]))
        for i, r in enumerate(results, 1):
            r["rank"] = i
    render(results, args.budget, args.people, spicy_ok, must_drink,
           real=real, coupon_count=coupon_count)


if __name__ == "__main__":
    main()
