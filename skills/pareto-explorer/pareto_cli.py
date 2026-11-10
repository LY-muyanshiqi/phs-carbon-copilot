#!/usr/bin/env python3
"""Pareto 前沿查询命令行。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pareto_core import ParetoError, analyze_pareto


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--preference", default="balanced", choices=["balanced", "low_peak", "low_carbon"])
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    payload["preference"] = args.preference
    try:
        result = analyze_pareto(payload)
    except ParetoError as exc:
        print(json.dumps({"ok": False, "error": exc.to_dict()}, ensure_ascii=False, indent=2))
        return 2

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    c = result["compromise"]
    print(f"前沿点数：{result['count']}")
    print(f"折中解：调峰深度 {c['zt_f_mw']:,.1f} MW，排放 {c['emissions_kg']/1e3:,.1f} t")
    print(f"最小调峰：{result['min_peak']['zt_f_mw']:,.1f} MW；最低排放：{result['min_carbon']['emissions_kg']/1e3:,.1f} t")
    return 0


if __name__ == "__main__":
    sys.exit(main())
