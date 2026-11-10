"""抽水蓄能减碳核算核心（Python 复刻《抽水蓄能减碳效益优化核算软件 V1.0》）。

对应 MATLAB 文件：
- evaluate_objective.m / tanpafangjisuan.m：火电碳排放强度与排放量
- process.m：有/无抽蓄两种场景对比
- main.m：全年汇总（kg -> 万吨）

约定：
- 功率单位 MW；时间步长 1 h；能量单位 MWh。
- 煤耗单位 g/kWh；排放强度单位 g/kWh；小时排放量单位 kg/h。
- 因此 排放强度(g/kWh) × 功率(MW) = kg/h，24 h 求和为 kg/d。
- 1 万吨 = 1e7 kg。

本模块只做“给定调度方案后的确定性核算”，不包含 NSGA-II 寻优。
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from typing import Any, Iterable, Sequence

METHOD_VERSION = "1.0.0"

# ---- MATLAB 中的固定常数（保持不变，便于与软著结果对齐）----
E_100 = 0.953
E_50 = 0.934
E_40 = 0.920
E_30 = 0.904
G_100 = 0.458
G_50 = 0.442
G_40 = 0.424
G_30 = 0.401
CQ = 0.9183          # 单位质量燃料产生的 CO2 系数
AUX_RATIO = 0.02     # 厂用电占比
SULFUR_CONTENT = 0.01
DESULFURIZATION_EFF = 0.95
M_S = 32
M_CO2 = 44
M_C = 12
ASH_ENERGY_RATIO = 0.0148
LIME_ENERGY_RATIO = 0.00392


class InputError(ValueError):
    """输入不合法，携带稳定的错误码，便于智能体向用户解释。"""

    def __init__(self, code: str, message: str, field: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "field": self.field}


@dataclass
class Params:
    """模型参数。默认值即软著 V1.0 的默认工况。"""

    zpump_mw: float = 1400.0          # 抽蓄装机容量 MW
    duration_h: float = 4.0           # 蓄能时长 h，容量 = zpump_mw × duration_h
    efficiency: float = 0.75          # 抽发综合效率
    min_load_ratio: float = 0.20      # 最小出力比例（20% 死区）
    oxidation_factor: float = 0.99    # 碳氧化率
    carbon_content: float = 0.70      # 收到基含碳量
    coal_deep_g_per_kwh: float = 370.0
    coal_mid_g_per_kwh: float = 330.0
    coal_base_g_per_kwh: float = 300.0

    @property
    def capacity_mwh(self) -> float:
        return self.zpump_mw * self.duration_h

    def validate(self) -> None:
        if not (0 < self.zpump_mw <= 10000):
            raise InputError("E_PARAM", "zpump_mw 应在 (0, 10000] MW 内", "zpump_mw")
        if not (0 < self.duration_h <= 24):
            raise InputError("E_PARAM", "duration_h 应在 (0, 24] h 内", "duration_h")
        if not (0 < self.efficiency <= 1):
            raise InputError("E_PARAM", "efficiency 应在 (0, 1] 内", "efficiency")
        if not (0 <= self.min_load_ratio < 1):
            raise InputError("E_PARAM", "min_load_ratio 应在 [0, 1) 内", "min_load_ratio")
        if not (0 < self.oxidation_factor <= 1):
            raise InputError("E_PARAM", "oxidation_factor 应在 (0, 1] 内", "oxidation_factor")
        if not (0 < self.carbon_content <= 1):
            raise InputError("E_PARAM", "carbon_content 应在 (0, 1] 内", "carbon_content")
        for name in ("coal_deep_g_per_kwh", "coal_mid_g_per_kwh", "coal_base_g_per_kwh"):
            value = getattr(self, name)
            if not (100 <= value <= 500):
                raise InputError("E_PARAM", f"{name} 应在 [100, 500] g/kWh 内", name)

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def _check_series(values: Sequence[float], name: str, length: int = 24) -> list[float]:
    try:
        series = [float(v) for v in values]
    except (TypeError, ValueError) as exc:
        raise InputError("E_INPUT", f"{name} 必须是数值数组", name) from exc
    if len(series) != length:
        raise InputError("E_LENGTH", f"{name} 长度应为 {length}，实际 {len(series)}", name)
    if any(not math.isfinite(v) for v in series):
        raise InputError("E_INPUT", f"{name} 含 NaN/Inf", name)
    if any(v < 0 for v in series):
        raise InputError("E_RANGE", f"{name} 不应为负值", name)
    return series


def simulate_storage(soc: Sequence[float], params: Params) -> tuple[list[float], list[float]]:
    """由 25 点 SOC 轨迹反推 24 小时抽蓄功率（正=发电，负=抽水）。

    与 evaluate_objective.m 完全一致：低于 20% 额定功率的动作被置零，
    超过额定功率的动作被限幅。返回 (npump_mw, 修正后的 soc)。
    """
    if len(soc) != 25:
        raise InputError("E_LENGTH", "soc 长度应为 25（含首末状态）", "soc")
    c = [float(v) for v in soc]
    if any(not math.isfinite(v) for v in c):
        raise InputError("E_INPUT", "soc 含 NaN/Inf", "soc")
    if any(v < 0 or v > 1 for v in c):
        raise InputError("E_RANGE", "soc 应在 [0, 1] 内", "soc")

    capacity = params.capacity_mwh
    npump = [0.0] * 24
    for i in range(24):
        if c[i + 1] <= c[i]:  # 发电（SOC 下降）
            power = (c[i] - c[i + 1]) * capacity
            if power < params.zpump_mw * params.min_load_ratio:
                power = 0.0
                c[i + 1] = c[i]
            if power > params.zpump_mw:
                power = params.zpump_mw
                c[i + 1] = c[i] - power / capacity
        if c[i + 1] > c[i]:  # 抽水（SOC 上升）
            power = (c[i] - c[i + 1]) * capacity / params.efficiency
            if power > -params.zpump_mw * params.min_load_ratio:
                power = 0.0
                c[i + 1] = c[i]
            if power < -params.zpump_mw:
                power = -params.zpump_mw
                c[i + 1] = c[i] - power * params.efficiency / capacity
        npump[i] = power
    return npump, c


def thermal_emissions(nt_mw: Sequence[float], params: Params) -> dict[str, Any]:
    """给定 24 小时火电出力，计算调峰深度、煤耗与 CO2 排放（kg/d）。"""
    nt = _check_series(nt_mw, "nt_mw")
    nt_max, nt_min = max(nt), min(nt)
    zt_f = (nt_max - nt_min) / 0.7
    nt_b = 0.0 if zt_f > nt_max else nt_max - zt_f
    th_max = zt_f

    base_intensity = (
        params.coal_base_g_per_kwh
        * params.oxidation_factor
        * params.carbon_content
        * M_CO2
        / M_C
    )
    base_emissions = base_intensity * nt_b  # kg/h

    hourly: list[dict[str, float]] = []
    total = 0.0
    for raw in nt:
        th = raw - nt_b
        th_eval = max(th, th_max * 0.3) if th_max > 0 else 0.0

        if th_max <= 1e-12:
            coal = params.coal_base_g_per_kwh
            ce1 = base_intensity
            ce2 = ce3 = 0.0
        elif th_eval < th_max * 0.4:
            coal = params.coal_deep_g_per_kwh
            e = E_30 + ((th_eval - th_max * 0.3) / (th_max * 0.1)) * (E_40 - E_30)
            g = G_30 + ((th_eval - th_max * 0.3) / (th_max * 0.1)) * (G_40 - G_30)
            ce1 = coal * params.oxidation_factor * params.carbon_content * M_CO2 / M_C
            ce2 = (
                coal * (1 - e / E_100) * CQ
                + coal * (1 - g / G_100) * CQ
                + AUX_RATIO * coal * CQ
            )
            ce3 = (
                coal * SULFUR_CONTENT * DESULFURIZATION_EFF * M_CO2 / M_S
                + coal * ASH_ENERGY_RATIO * CQ
                + coal * LIME_ENERGY_RATIO * CQ
            )
        elif th_eval < th_max * 0.5:
            coal = params.coal_mid_g_per_kwh
            e = E_40 + ((th_eval - th_max * 0.4) / (th_max * 0.1)) * (E_50 - E_40)
            g = G_40 + ((th_eval - th_max * 0.4) / (th_max * 0.1)) * (G_50 - G_40)
            ce1 = coal * params.oxidation_factor * params.carbon_content * M_CO2 / M_C
            ce2 = (
                coal * (1 - e / E_100) * CQ
                + coal * (1 - g / G_100) * CQ
                + AUX_RATIO * coal * CQ
            )
            ce3 = 0.0
        else:
            coal = params.coal_base_g_per_kwh
            ce1 = coal * params.oxidation_factor * params.carbon_content * M_CO2 / M_C
            ce2 = ce3 = 0.0

        intensity = ce1 + ce2 + ce3
        emissions = intensity * th_eval + base_emissions
        total += emissions
        hourly.append(
            {
                "thermal_mw": round(raw, 3),
                "th_mw": round(th_eval, 3),
                "coal_g_per_kwh": round(coal, 3),
                "intensity_g_per_kwh": round(intensity, 3),
                "emissions_kg": round(emissions, 3),
            }
        )

    avg_intensity = total / sum(nt) if sum(nt) > 0 else 0.0
    return {
        "zt_f_mw": round(zt_f, 3),
        "nt_b_mw": round(nt_b, 3),
        "base_intensity_g_per_kwh": round(base_intensity, 3),
        "avg_intensity_g_per_kwh": round(avg_intensity, 3),
        "emissions_kg": round(total, 3),
        "hourly": hourly,
    }


def heuristic_soc(
    load: Sequence[float],
    hydro: Sequence[float],
    wind: Sequence[float],
    solar: Sequence[float],
    params: Params,
) -> list[float]:
    """无优化结果时的确定性启发式调度：低谷抽水、高峰发电，首末 SOC 均为 0.5。

    只用于演示与缺省场景，不替代 NSGA-II。返回 25 点 SOC。
    """
    load = _check_series(load, "load_mw")
    hydro = _check_series(hydro, "hydro_mw")
    wind = _check_series(wind, "wind_mw")
    solar = _check_series(solar, "solar_mw")
    net = [load[i] - hydro[i] - wind[i] - solar[i] for i in range(24)]

    n = max(1, min(8, int(round(params.duration_h))))
    order = sorted(range(24), key=lambda i: (net[i], i))
    charge_hours = set(order[:n])
    discharge_hours = set(order[-n:])
    # 极端情况下避免同一小时既抽又发
    for hour in list(charge_hours & discharge_hours):
        discharge_hours.discard(hour)

    delta = 0.4 / n
    soc = [0.5]
    for t in range(24):
        if t in charge_hours:
            soc.append(min(0.95, soc[-1] + delta))
        elif t in discharge_hours:
            soc.append(max(0.05, soc[-1] - delta))
        else:
            soc.append(soc[-1])
    soc[24] = 0.5
    return [round(v, 6) for v in soc]


def evaluate_day(
    load_mw: Sequence[float],
    hydro_mw: Sequence[float],
    wind_mw: Sequence[float],
    solar_mw: Sequence[float],
    params: Params | None = None,
    soc: Sequence[float] | None = None,
    date: str | None = None,
) -> dict[str, Any]:
    """核算单日：有抽蓄 vs 无抽蓄，返回功率、排放与减碳量。"""
    params = params or Params()
    params.validate()

    load = _check_series(load_mw, "load_mw")
    hydro = _check_series(hydro_mw, "hydro_mw")
    wind = _check_series(wind_mw, "wind_mw")
    solar = _check_series(solar_mw, "solar_mw")

    warnings: list[str] = []
    if soc is None:
        soc = heuristic_soc(load, hydro, wind, solar, params)
        warnings.append("未提供调度方案，已使用“低谷抽水、高峰发电”启发式调度；结果仅用于演示。")
    else:
        try:
            soc = [float(v) for v in soc]
        except (TypeError, ValueError) as exc:
            raise InputError("E_INPUT", "soc 必须是数值数组", "soc") from exc
        if len(soc) != 25:
            raise InputError("E_LENGTH", "soc 长度应为 25（含首末状态）", "soc")
        if abs(soc[0] - 0.5) > 1e-9 or abs(soc[24] - 0.5) > 1e-9:
            warnings.append("SOC 首末状态不是 0.5，周期约束不满足；MATLAB 原模型会将该解判为不可行。")

    npump, soc_used = simulate_storage(soc, params)
    renewable = [hydro[i] + wind[i] + solar[i] for i in range(24)]
    nt = [load[i] - renewable[i] - npump[i] for i in range(24)]
    nt2 = [load[i] - renewable[i] for i in range(24)]

    if any(v < -1e-6 for v in nt) or any(v < -1e-6 for v in nt2):
        raise InputError(
            "E_RANGE",
            "火电出力为负：新能源/抽蓄出力超过负荷，请检查负荷与风光数据口径，或调整调度方案。",
            "load_mw",
        )

    with_phs = thermal_emissions(nt, params)
    without_phs = thermal_emissions(nt2, params)
    reduction = without_phs["emissions_kg"] - with_phs["emissions_kg"]
    rate = (reduction / without_phs["emissions_kg"] * 100) if without_phs["emissions_kg"] else 0.0

    if reduction < 0:
        warnings.append("本日减碳量为负：抽蓄抽水消耗的电量由高碳火电补足，超过了替代高煤耗调峰带来的收益。")

    return {
        "date": date,
        "params": params.to_dict(),
        "capacity_mwh": round(params.capacity_mwh, 3),
        "soc": [round(v, 6) for v in soc_used],
        "npump_mw": [round(v, 3) for v in npump],
        "thermal_with_phs_mw": [round(v, 3) for v in nt],
        "thermal_without_phs_mw": [round(v, 3) for v in nt2],
        "with_phs": with_phs,
        "without_phs": without_phs,
        "reduction_kg": round(reduction, 3),
        "reduction_t": round(reduction / 1000, 3),
        "reduction_10kt": round(reduction / 1e7, 6),
        "reduction_rate_pct": round(rate, 4),
        "warnings": warnings,
    }


def evaluate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """执行 CLI / HTTP 的统一入口，返回可直接序列化的结果。"""
    if not isinstance(payload, dict):
        raise InputError("E_INPUT", "请求体应为 JSON 对象")

    param_payload = payload.get("params") or {}
    if not isinstance(param_payload, dict):
        raise InputError("E_INPUT", "params 应为对象", "params")
    allowed = {f.name for f in fields(Params)}
    unknown = set(param_payload) - allowed
    if unknown:
        raise InputError("E_INPUT", f"未知参数：{', '.join(sorted(unknown))}", "params")
    coerced: dict[str, float] = {}
    for key, value in param_payload.items():
        try:
            coerced[key] = float(value)
        except (TypeError, ValueError) as exc:
            raise InputError("E_INPUT", f"参数 {key} 必须是数值", key) from exc
    params = Params(**coerced)
    params.validate()

    days = payload.get("days")
    if not isinstance(days, list) or not days:
        raise InputError("E_INPUT", "days 应为非空数组", "days")

    results: list[dict[str, Any]] = []
    for index, day in enumerate(days):
        if not isinstance(day, dict):
            raise InputError("E_INPUT", f"days[{index}] 应为对象", f"days[{index}]")
        try:
            result = evaluate_day(
                day.get("load_mw"),
                day.get("hydro_mw"),
                day.get("wind_mw"),
                day.get("solar_mw"),
                params=params,
                soc=day.get("soc"),
                date=day.get("date"),
            )
        except InputError as exc:
            raise InputError(exc.code, f"days[{index}]：{exc.message}", exc.field) from exc
        results.append(result)

    total_reduction = sum(item["reduction_kg"] for item in results)
    total_with = sum(item["with_phs"]["emissions_kg"] for item in results)
    total_without = sum(item["without_phs"]["emissions_kg"] for item in results)
    total_rate = (total_reduction / total_without * 100) if total_without else 0.0

    return {
        "ok": True,
        "method_version": METHOD_VERSION,
        "model": "抽水蓄能—火电深度调峰协同减碳核算（软著 V1.0 口径）",
        "params": params.to_dict(),
        "summary": {
            "days": len(results),
            "reduction_kg": round(total_reduction, 3),
            "reduction_t": round(total_reduction / 1000, 3),
            "reduction_10kt": round(total_reduction / 1e7, 6),
            "reduction_rate_pct": round(total_rate, 4),
            "emissions_with_phs_kg": round(total_with, 3),
            "emissions_without_phs_kg": round(total_without, 3),
        },
        "days": results,
        "assumptions": [
            "1 h 时间步长；功率 MW；煤耗与排放强度 g/kWh；排放量 kg。",
            "有抽蓄场景：火电 = 负荷 - 水/风/光 - 抽蓄（正发电、负抽水）。",
            "无抽蓄场景：火电 = 负荷 - 水/风/光。",
            "抽蓄效率默认 0.75；低于 20% 额定功率的动作按 0 处理；SOC 首末均为 0.5。",
            "未提供 SOC 时使用启发式调度，不等同于 NSGA-II 最优解。",
        ],
        "disclaimer": "本结果用于方案对比与教学演示，不构成电网调度指令或碳资产签发依据。",
    }
