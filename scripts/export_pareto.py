#!/usr/bin/env python3
"""从 A.mat 导出某一天的 Pareto 前沿点。"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import scipy.io as sio

ROOT = Path(__file__).resolve().parents[1]
MAT = ROOT / "data" / "local" / "A.mat"
OUT = ROOT / "skills" / "pareto-explorer" / "examples" / "pareto_day321.json"


def main() -> None:
    A = sio.loadmat(MAT)["A"]
    day = 320  # 第 321 天
    f1 = A[:, 23, day]
    f2 = A[:, 24, day]
    valid = (f1 < 1e9) & (f2 < 1e12)
    points = [
        {"zt_f_mw": round(float(a), 3), "emissions_kg": round(float(b), 3)}
        for a, b in zip(f1[valid], f2[valid])
    ]
    payload = {
        "project": "示例：第 321 天 NSGA-II Pareto 前沿",
        "date": "2026-11-17",
        "source": "A.mat, day 321, 100 individuals",
        "points": points,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已导出 {len(points)} 个前沿点：{OUT}")


if __name__ == "__main__":
    main()
