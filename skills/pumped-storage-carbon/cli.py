#!/usr/bin/env python3
"""蓄能碳效参谋 · 核算 SKILL 命令行入口。

用法：
  python cli.py --demo
  python cli.py --input examples/input_day.json
  python cli.py --input examples/input_year.json --output outputs/year.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from carbon_core import InputError, evaluate_payload

HERE = Path(__file__).resolve().parent


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"找不到输入文件：{path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"输入不是合法 JSON：{exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="抽水蓄能减碳核算（软著 V1.0 口径）")
    parser.add_argument("-i", "--input", type=Path, help="输入 JSON 路径")
    parser.add_argument("-o", "--output", type=Path, help="输出 JSON 路径；缺省只打印摘要")
    parser.add_argument("--demo", action="store_true", help="运行内置单日示例")
    parser.add_argument("--indent", type=int, default=2, help="输出缩进，默认 2")
    parser.add_argument("--quiet", action="store_true", help="只写文件，不打印摘要")
    args = parser.parse_args()

    if args.demo:
        input_path = HERE / "examples" / "input_day.json"
    elif args.input:
        input_path = args.input
    else:
        parser.error("请提供 --input 或 --demo")

    payload = _load(input_path)
    try:
        result = evaluate_payload(payload)
    except InputError as exc:
        result = {"ok": False, "error": exc.to_dict()}
        print(json.dumps(result, ensure_ascii=False, indent=args.indent))
        return 2

    text = json.dumps(result, ensure_ascii=False, indent=args.indent)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")

    if not args.quiet:
        s = result["summary"]
        print("=" * 58)
        print("蓄能碳效参谋 · 核算完成")
        print(f"核算天数：{s['days']} 天")
        print(f"减碳量：{s['reduction_t']:,.1f} t  ({s['reduction_10kt']:.4f} 万吨)")
        print(f"减排率：{s['reduction_rate_pct']:.2f}%")
        print(f"有抽蓄排放：{s['emissions_with_phs_kg']/1e3:,.1f} t")
        print(f"无抽蓄排放：{s['emissions_without_phs_kg']/1e3:,.1f} t")
        if args.output:
            print(f"结果文件：{args.output}")
        warnings = result["days"][0].get("warnings") or []
        if warnings:
            print("提示：")
            for item in warnings[:3]:
                print(f"  - {item}")
        print("=" * 58)
    return 0


if __name__ == "__main__":
    sys.exit(main())
