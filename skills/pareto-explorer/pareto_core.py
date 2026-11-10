#!/usr/bin/env python3
"""Pareto 前沿分析：从 NSGA-II 解集中选折中点、两端极值点与拐点。"""

from __future__ import annotations

import math
from typing import Any


class ParetoError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


WEIGHTS = {
    "balanced": (0.5, 0.5),
    "low_peak": (0.8, 0.2),
    "low_carbon": (0.2, 0.8),
}


def analyze_pareto(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ParetoError("E_INPUT", "请求体应为 JSON 对象")
    points = payload.get("points")
    if not isinstance(points, list) or len(points) < 3:
        raise ParetoError("E_INPUT", "points 至少需要 3 个前沿点")

    clean: list[dict[str, float]] = []
    for index, item in enumerate(points):
        if not isinstance(item, dict):
            raise ParetoError("E_INPUT", f"points[{index}] 应为对象")
        try:
            f1 = float(item["zt_f_mw"])
            f2 = float(item["emissions_kg"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ParetoError("E_INPUT", f"points[{index}] 需要数值型 zt_f_mw、emissions_kg") from exc
        if not (math.isfinite(f1) and math.isfinite(f2)) or f1 < 0 or f2 <= 0:
            raise ParetoError("E_RANGE", f"points[{index}] 数值超出合理范围")
        clean.append({"zt_f_mw": f1, "emissions_kg": f2})

    preference = payload.get("preference", "balanced")
    if preference not in WEIGHTS:
        raise ParetoError("E_PARAM", f"preference 只能是 {', '.join(WEIGHTS)}")

    f1_values = [p["zt_f_mw"] for p in clean]
    f2_values = [p["emissions_kg"] for p in clean]
    f1_min, f1_max = min(f1_values), max(f1_values)
    f2_min, f2_max = min(f2_values), max(f2_values)
    span1 = f1_max - f1_min or 1.0
    span2 = f2_max - f2_min or 1.0

    w1, w2 = WEIGHTS[preference]
    for point in clean:
        x1 = (point["zt_f_mw"] - f1_min) / span1
        x2 = (point["emissions_kg"] - f2_min) / span2
        point["norm_peak"] = round(x1, 6)
        point["norm_carbon"] = round(x2, 6)
        point["score"] = round((1 - x1) * w1 + (1 - x2) * w2, 6)

    compromise = max(clean, key=lambda p: p["score"])
    min_peak = min(clean, key=lambda p: (p["zt_f_mw"], p["emissions_kg"]))
    min_carbon = min(clean, key=lambda p: (p["emissions_kg"], p["zt_f_mw"]))
    knee = max(clean, key=lambda p: p["norm_peak"] + p["norm_carbon"])

    for point in clean:
        point["role"] = "normal"
    compromise["role"] = "compromise"
    min_peak["role"] = "min_peak"
    min_carbon["role"] = "min_carbon"
    if knee is not compromise:
        knee["role"] = "knee"

    clean.sort(key=lambda p: p["zt_f_mw"])
    return {
        "ok": True,
        "preference": preference,
        "count": len(clean),
        "ranges": {
            "zt_f_mw": [round(f1_min, 3), round(f1_max, 3)],
            "emissions_kg": [round(f2_min, 3), round(f2_max, 3)],
        },
        "compromise": compromise,
        "min_peak": min_peak,
        "min_carbon": min_carbon,
        "knee": knee,
        "points": clean,
        "interpretation": (
            "min_peak 追求最小调峰深度；min_carbon 追求最低排放；"
            "compromise 按偏好权重在归一化目标上取综合最优；knee 是前沿拐点。"
        ),
    }
