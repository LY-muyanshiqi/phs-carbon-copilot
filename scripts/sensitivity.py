#!/usr/bin/env python3
"""参数敏感性：固定 NSGA-II 调度轨迹，单因素扫描装机、效率、死区。"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "pumped-storage-carbon"))

from carbon_core import Params, evaluate_payload  # noqa: E402

EXAMPLES = ROOT / "skills" / "pumped-storage-carbon" / "examples"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

BASE = json.loads((EXAMPLES / "input_year.json").read_text(encoding="utf-8"))
BASE_PARAMS = dict(BASE["params"])
BASE_REDUCTION = evaluate_payload(BASE)["summary"]["reduction_t"]

SWEEPS = {
    "zpump_mw": [700, 1000, 1400, 1800, 2100],
    "efficiency": [0.70, 0.75, 0.80],
    "min_load_ratio": [0.10, 0.20, 0.30],
}


def run(values: dict) -> float:
    payload = json.loads(json.dumps(BASE))
    payload["params"].update(values)
    return evaluate_payload(payload)["summary"]["reduction_t"]


def main() -> None:
    rows: list[dict] = []
    for name, values in SWEEPS.items():
        for value in values:
            reduction = run({name: value})
            rows.append(
                {
                    "parameter": name,
                    "value": value,
                    "annual_reduction_t": round(reduction, 3),
                    "annual_reduction_10kt": round(reduction / 1e4, 4),
                    "delta_vs_base_pct": round((reduction / BASE_REDUCTION - 1) * 100, 3),
                }
            )
            print(f"{name}={value}: {reduction:,.1f} t ({rows[-1]['delta_vs_base_pct']:+.2f}%)")

    path = OUT / "sensitivity.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"基础情景：{BASE_REDUCTION:,.1f} t")
    print(f"已写出：{path}")


if __name__ == "__main__":
    main()
