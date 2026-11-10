#!/usr/bin/env python3
"""从 data/raw 的四个 365x24 文本生成示例输入 JSON。

若 data/local/AA.mat 存在，则把 NSGA-II 折中解的 SOC 轨迹一并写入，
使示例结果与软著 MATLAB 结果一致；否则不写 SOC，由核算器使用启发式调度。
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import scipy.io as sio

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "skills" / "pumped-storage-carbon" / "examples"
AA_PATH = ROOT / "data" / "local" / "AA.mat"


def read(name: str) -> np.ndarray:
    return np.loadtxt(RAW / name)


def date_of(index: int) -> str:
    return (dt.date(2026, 1, 1) + dt.timedelta(days=index)).isoformat()


def day_payload(load, hydro, wind, solar, index: int, soc=None) -> dict:
    item = {
        "date": date_of(index),
        "load_mw": [round(float(v), 6) for v in load[index]],
        "hydro_mw": [round(float(v), 6) for v in hydro[index]],
        "wind_mw": [round(float(v), 6) for v in wind[index]],
        "solar_mw": [round(float(v), 6) for v in solar[index]],
    }
    if soc is not None:
        item["soc"] = [round(float(v), 9) for v in soc]
    return item


def main() -> None:
    load, hydro, wind, solar = (read(n) for n in ("FH.txt", "hydro.txt", "wind.txt", "solar.txt"))
    socs = None
    if AA_PATH.exists():
        AA = sio.loadmat(AA_PATH)["AA"]
        socs = [np.concatenate(([0.5], AA[i, :23], [0.5])) for i in range(AA.shape[0])]
        print(f"已读取优化解：{AA.shape[0]} 天")

    base_params = {
        "zpump_mw": 1400,
        "duration_h": 4,
        "efficiency": 0.75,
        "min_load_ratio": 0.2,
        "oxidation_factor": 0.99,
        "carbon_content": 0.7,
        "coal_deep_g_per_kwh": 370,
        "coal_mid_g_per_kwh": 330,
        "coal_base_g_per_kwh": 300,
    }
    OUT.mkdir(parents=True, exist_ok=True)

    best = 320  # 第 321 天，全年减碳量最高
    single = {
        "project": "示例：某省级电网单日抽蓄减碳核算（NSGA-II 折中解）",
        "params": base_params,
        "days": [day_payload(load, hydro, wind, solar, best, None if socs is None else socs[best])],
    }
    (OUT / "input_day.json").write_text(json.dumps(single, ensure_ascii=False, indent=2), encoding="utf-8")

    three = {
        "project": "示例：连续三日核算（NSGA-II 折中解）",
        "params": base_params,
        "days": [
            day_payload(load, hydro, wind, solar, i, None if socs is None else socs[i])
            for i in (319, 320, 321)
        ],
    }
    (OUT / "input_3days.json").write_text(json.dumps(three, ensure_ascii=False, indent=2), encoding="utf-8")

    year = {
        "project": "示例：全年 365 天核算（NSGA-II 折中解）",
        "params": base_params,
        "days": [
            day_payload(load, hydro, wind, solar, i, None if socs is None else socs[i])
            for i in range(365)
        ],
    }
    (OUT / "input_year.json").write_text(json.dumps(year, ensure_ascii=False, indent=2), encoding="utf-8")
    print("已生成：", [p.name for p in OUT.glob("input_*.json")])


if __name__ == "__main__":
    main()
