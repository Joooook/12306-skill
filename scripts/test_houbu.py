#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""候补状态显示的回归测试。

改动 `12306_apis.py` 里候补相关代码后跑一遍，确认没有回归：

    python3 test_houbu.py

设计原则：**断言结构，不断言票况**。票是实时变动的，把它当断言必然误报；
这里只检查字段是否齐全、格式是否合法、分支是否可达。
"""
import importlib.util
import json
import os
import subprocess
import sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(HERE, "12306_apis.py")

# ---------- 单元测试：describe_houbu_state（不联网） ----------
spec = importlib.util.spec_from_file_location("api", CLI)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %s %s%s" % ("✅" if cond else "❌", name,
                         ("  → " + detail) if detail and not cond else ""))


print("═══ 1. 单元测试：describe_houbu_state ═══")
check("flag='0' + limit 空（全有票）→ None",
      m.describe_houbu_state({"houbu_train_flag": "0"}) is None)
check("flag 缺失 → None",
      m.describe_houbu_state({}) is None)
check("flag='0' 但 limit 非空 → 仍显示（防漏报）",
      m.describe_houbu_state(
          {"houbu_train_flag": "0", "houbu_seat_limit": "J"}) is not None)
check("flag=1 + 空串 → 可提交",
      m.describe_houbu_state(
          {"houbu_train_flag": "1", "houbu_seat_limit": ""}) == "🎫 候补：可提交")
check("flag=1 + 字段缺失 → 可提交",
      m.describe_houbu_state({"houbu_train_flag": "1"}) == "🎫 候补：可提交")

full = m.describe_houbu_state(
    {"houbu_train_flag": "1", "houbu_seat_limit": "JOI"})
check("'JOI' → 译出全部三个席别名",
      all(s in (full or "") for s in ("二等卧", "一等卧", "二等座")),
      repr(full))
check("'JOI' → 含警示语义", "已满" in (full or ""), repr(full))

part = m.describe_houbu_state(
    {"houbu_train_flag": "1", "houbu_seat_limit": "JI"})
check("'JI' → 不含二等座", "二等座" not in (part or ""), repr(part))

short = m.describe_houbu_state(
    {"houbu_train_flag": "1", "houbu_seat_limit": "J"}, short=True)
check("short 模式无 emoji", "🎫" not in short and "⚠️" not in short, repr(short))
check("short 模式可提交返回 '-'",
      m.describe_houbu_state({"houbu_train_flag": "1"}, short=True) == "-")
check("未知席别代码不崩",
      "Z" in (m.describe_houbu_state(
          {"houbu_train_flag": "1", "houbu_seat_limit": "Z"}) or ""))
print()

# ---------- 端到端 ----------
TODAY = date.today()
D_SOON = (TODAY + timedelta(days=3)).strftime("%Y-%m-%d")
D_FAR = (TODAY + timedelta(days=20)).strftime("%Y-%m-%d")
ROUTE = ["--from_station", "北京", "--to_station", "南昌",
         "--train_filter_flags", "D"]


def run(args):
    r = subprocess.run([sys.executable, CLI] + args,
                       capture_output=True, text=True, timeout=240)
    return r.stdout + r.stderr


def parse_json(out):
    i = out.find("[")
    if i < 0:
        return None
    try:
        return json.loads(out[i:])
    except Exception:
        return None


print("═══ 2. JSON 字段完整性（%s）═══" % D_SOON)
data = parse_json(run(["get-tickets", "--date", D_SOON] + ROUTE
                      + ["--format", "json"]))
if data is None:
    check("JSON 可解析", False, "接口未返回 JSON（网络或日期问题）")
else:
    check("JSON 可解析（%d 趟车）" % len(data), True)
    want = ["houbu_train_flag", "houbu_seat_limit", "seat_types",
            "end_station_telecode", "at_final_station"]
    for k in want:
        check("字段存在: %s" % k, k in data[0])
    check("at_final_station 是 bool",
          isinstance(data[0].get("at_final_station"), bool))
    # 分支可达性：报告该线路上是否出现"候补已满"
    n_full = sum(1 for d in data if d.get("houbu_seat_limit"))
    print("  ℹ️  该线路 %d 趟中 %d 趟显示候选补已满" % (len(data), n_full))
    if n_full == 0:
        print("  ℹ️  本次未覆盖「已满」分支（票况使然，非缺陷）")
print()

print("═══ 3. CSV 列数一致性（%s）═══" % D_SOON)
csv_out = run(["get-tickets", "--date", D_SOON] + ROUTE + ["--format", "csv"])
rows = [r for r in csv_out.strip().splitlines() if r.strip()]
if not rows:
    check("CSV 有输出", False, "空输出")
else:
    header = rows[0].split(",")
    check("表头末列为「候补」", header[-1] == "候补", repr(header[-1]))
    check("表头 9 列", len(header) == 9, "实际 %d 列" % len(header))
    for r in rows[1:]:
        cols = r.split(",")
        # 票价列内部含逗号，故按「前 6 列 + 尾部 2 列」校验
        ok = len(cols) >= 9
        if not ok:
            check("数据行列数 ≥9", False, r[:80])
            break
    else:
        check("所有数据行列数 ≥9（%d 行）" % (len(rows) - 1), True)
print()

print("═══ 4. text 输出格式 ═══")
txt = run(["get-tickets", "--date", D_SOON] + ROUTE
          + ["--sort_flag", "startTime"])
lines = txt.splitlines()
check("有车次行", any(l and l[0].isalpha() for l in lines))
houbu_lines = [l for l in lines if "候补" in l]
check("出现候补行（%d 行）" % len(houbu_lines), len(houbu_lines) > 0)
bad = [l for l in houbu_lines
       if not (l.startswith("  🎫") or l.startswith("  ⚠️"))]
check("候补行格式正确（2 空格缩进 + 图标）", not bad,
      "异常行: %s" % bad[:2])
print()

print("═══ 5. 未开售日期不应崩（%s）═══" % D_FAR)
out = run(["get-tickets", "--date", D_FAR] + ROUTE)
crashed = "Traceback" in out or "Error: Error" in out
check("无 Python 崩溃", not crashed, out[:200])
if "Get tickets data failed" in out or not out.strip():
    print("  ℹ️  返回错误/空 —— 符合「预售期外」的预期，非缺陷")
print()

print("═" * 52)
print("  通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
if FAIL:
    print("  失败项：")
    for f in FAIL:
        print("    - %s" % f)
print("═" * 52)
sys.exit(1 if FAIL else 0)
