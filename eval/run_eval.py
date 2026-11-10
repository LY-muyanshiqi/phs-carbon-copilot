#!/usr/bin/env python3
"""运行 20 条自动化核算评测 + 5 条人工对话评测。"""

from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "pumped-storage-carbon"))

from carbon_core import InputError, evaluate_payload  # noqa: E402

EXAMPLES = ROOT / "skills" / "pumped-storage-carbon" / "examples"
CASES = ROOT / "eval" / "test_cases.jsonl"

BASES = {
    "day": json.loads((EXAMPLES / "input_day.json").read_text(encoding="utf-8")),
    "3days": json.loads((EXAMPLES / "input_3days.json").read_text(encoding="utf-8")),
    "year": json.loads((EXAMPLES / "input_year.json").read_text(encoding="utf-8")),
}


def build(case: dict) -> object:
    op = case.get("op") or {}
    if "payload" in op:
        return op["payload"]
    payload = copy.deepcopy(BASES[case["base"]])
    if op.get("days_empty"):
        payload["days"] = []
    if op.get("remove_soc"):
        payload["days"][0].pop("soc", None)
    for key, value in (op.get("params") or {}).items():
        payload["params"][key] = value
    for key, value in (op.get("day") or {}).items():
        payload["days"][0][key] = value
    for key in op.get("drop_day_fields") or []:
        payload["days"][0].pop(key, None)
    for key, length in (op.get("truncate_day_fields") or {}).items():
        payload["days"][0][key] = payload["days"][0][key][:length]
    if "soc_length" in op:
        payload["days"][0]["soc"] = payload["days"][0]["soc"][: op["soc_length"]]
    if "soc_start" in op:
        payload["days"][0]["soc"][0] = op["soc_start"]
    if op.get("load_all") is not None:
        payload["days"][0]["load_mw"] = [op["load_all"]] * 24
    if op.get("duplicate_day"):
        payload["days"] = [payload["days"][0], copy.deepcopy(payload["days"][0])]
        trunc = op.get("duplicate_day_truncate") or {}
        if trunc:
            payload["days"][1][trunc["field"]] = payload["days"][1][trunc["field"]][: trunc["length"]]
    return payload


def run_tool(case: dict) -> tuple[bool, str]:
    payload = build(case)
    expect = case["expect"]
    started = time.perf_counter()
    try:
        result = evaluate_payload(payload)  # type: ignore[arg-type]
        elapsed = time.perf_counter() - started
    except InputError as exc:
        elapsed = time.perf_counter() - started
        result = {"ok": False, "error": exc.to_dict()}
    except Exception as exc:  # noqa: BLE001
        return False, f"未预期异常：{type(exc).__name__}: {exc}"

    if bool(result.get("ok")) != bool(expect.get("ok")):
        return False, f"ok 期望 {expect.get('ok')}，实际 {result.get('ok')}；{result}"
    if not result.get("ok"):
        actual = (result.get("error") or {}).get("code")
        if actual != expect.get("error_code"):
            return False, f"错误码期望 {expect.get('error_code')}，实际 {actual}"
        return True, f"{actual}（{elapsed*1000:.0f} ms）"

    summary = result["summary"]
    if "days" in expect and summary["days"] != expect["days"]:
        return False, f"天数期望 {expect['days']}，实际 {summary['days']}"
    if "reduction_t" in expect:
        tol = float(expect.get("tol", 1.0))
        if abs(summary["reduction_t"] - expect["reduction_t"]) > tol:
            return False, f"减碳量期望 {expect['reduction_t']}±{tol}，实际 {summary['reduction_t']}"
    if "warnings_contains" in expect:
        text = " ".join(w for day in result["days"] for w in day.get("warnings", []))
        if expect["warnings_contains"] not in text:
            return False, f"警告中未找到“{expect['warnings_contains']}”；实际：{text or '无'}"
    if "elapsed_max_s" in expect and elapsed > expect["elapsed_max_s"]:
        return False, f"耗时 {elapsed:.3f}s 超过上限 {expect['elapsed_max_s']}s"
    detail = f"{summary['days']} 天，{summary['reduction_t']:,.1f} t，{elapsed*1000:.0f} ms"
    return True, detail


def main() -> int:
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]
    passed = failed = manual = 0
    rows: list[tuple[str, str, str, str]] = []
    for case in cases:
        if case["type"] == "chat":
            manual += 1
            rows.append((case["id"], "人工", case["name"], "关键词：" + " / ".join(case["expect_keywords"])))
            continue
        ok, detail = run_tool(case)
        if ok:
            passed += 1
            rows.append((case["id"], "通过", case["name"], detail))
        else:
            failed += 1
            rows.append((case["id"], "失败", case["name"], detail))

    width = max(len(row[2]) for row in rows)
    print(f"{'ID':<5}{'结果':<6}{'用例':<{width + 2}}详情")
    print("-" * (80 + width))
    for cid, status, name, detail in rows:
        print(f"{cid:<5}{status:<6}{name:<{width + 2}}{detail}")
    print("-" * (80 + width))
    print(f"自动化：{passed} 通过 / {failed} 失败；人工对话：{manual} 条待按关键词复核")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
