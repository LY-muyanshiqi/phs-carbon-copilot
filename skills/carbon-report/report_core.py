#!/usr/bin/env python3
"""把核算结果 JSON 转成 Markdown / HTML 报告。"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _fmt(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}"


def build_markdown(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        raise ValueError("结果 JSON 不是成功核算结果")
    s = result["summary"]
    params = result["params"]
    lines: list[str] = []
    lines.append("# 抽水蓄能减碳核算报告\n")
    lines.append(f"> 模型版本：{result.get('method_version', '-')}  ")
    lines.append(f"> 核算天数：{s['days']} 天  ")
    lines.append("> 生成方式：蓄能碳效参谋 · 报告生成 SKILL\n")

    lines.append("## 一、结论\n")
    lines.append(
        f"本次核算减碳 **{_fmt(s['reduction_t'])} t**"
        f"（**{s['reduction_10kt']:.4f} 万吨**），减排率 **{s['reduction_rate_pct']:.2f}%**。"
    )
    lines.append(
        f"有抽蓄情景排放 {_fmt(s['emissions_with_phs_kg'] / 1e3)} t，"
        f"无抽蓄情景排放 {_fmt(s['emissions_without_phs_kg'] / 1e3)} t。\n"
    )

    lines.append("## 二、核算口径\n")
    lines.append("| 参数 | 取值 | 单位 |")
    lines.append("|---|---:|---|")
    labels = [
        ("zpump_mw", "抽蓄装机", "MW"),
        ("duration_h", "蓄能时长", "h"),
        ("efficiency", "抽发综合效率", "—"),
        ("min_load_ratio", "最小出力比例", "—"),
        ("oxidation_factor", "碳氧化率", "—"),
        ("carbon_content", "收到基含碳量", "—"),
        ("coal_deep_g_per_kwh", "深度调峰煤耗", "g/kWh"),
        ("coal_mid_g_per_kwh", "中度调峰煤耗", "g/kWh"),
        ("coal_base_g_per_kwh", "基荷煤耗", "g/kWh"),
    ]
    for key, label, unit in labels:
        lines.append(f"| {label} | {params.get(key, '-')} | {unit} |")
    lines.append("")

    lines.append("## 三、分日结果\n")
    lines.append("| 日期 | 有抽蓄排放（t） | 无抽蓄排放（t） | 减碳（t） | 减排率 |")
    lines.append("|---|---:|---:|---:|---:|")
    for day in result["days"]:
        lines.append(
            f"| {day.get('date') or '-'} | {_fmt(day['with_phs']['emissions_kg'] / 1e3)} | "
            f"{_fmt(day['without_phs']['emissions_kg'] / 1e3)} | "
            f"{_fmt(day['reduction_t'])} | {day['reduction_rate_pct']:.2f}% |"
        )
    lines.append("")

    warnings = [(day.get("date") or "-", w) for day in result["days"] for w in day.get("warnings", [])]
    lines.append("## 四、假设与提示\n")
    for item in result.get("assumptions", []):
        lines.append(f"- {item}")
    if warnings:
        lines.append("\n**本次核算的警告：**\n")
        for date, warning in warnings:
            lines.append(f"- {date}：{warning}")
    else:
        lines.append("\n本次核算未触发数据/调度警告。")
    lines.append("")

    lines.append("## 五、边界\n")
    lines.append(result.get("disclaimer", "结果仅用于科研、教学与方案比较。"))
    lines.append("")
    lines.append("---\n")
    lines.append("本报告由蓄能碳效参谋自动生成；计算数值来自确定性核算工具，文字解释由智能体生成。")
    return "\n".join(lines)


def build_html(result: dict[str, Any]) -> str:
    s = result["summary"]
    params = result["params"]
    rows = "".join(
        f"<tr><td>{html.escape(str(day.get('date') or '-'))}</td>"
        f"<td>{_fmt(day['with_phs']['emissions_kg'] / 1e3)}</td>"
        f"<td>{_fmt(day['without_phs']['emissions_kg'] / 1e3)}</td>"
        f"<td>{_fmt(day['reduction_t'])}</td>"
        f"<td>{day['reduction_rate_pct']:.2f}%</td></tr>"
        for day in result["days"]
    )
    warnings = "".join(
        f"<li>{html.escape(str(day.get('date') or '-'))}：{html.escape(w)}</li>"
        for day in result["days"]
        for w in day.get("warnings", [])
    ) or "<li>无</li>"
    param_rows = "".join(
        f"<tr><td>{html.escape(label)}</td><td>{params.get(key, '-')}</td><td>{unit}</td></tr>"
        for key, label, unit in [
            ("zpump_mw", "抽蓄装机", "MW"),
            ("duration_h", "蓄能时长", "h"),
            ("efficiency", "抽发综合效率", "—"),
            ("min_load_ratio", "最小出力比例", "—"),
            ("oxidation_factor", "碳氧化率", "—"),
            ("carbon_content", "收到基含碳量", "—"),
            ("coal_deep_g_per_kwh", "深度调峰煤耗", "g/kWh"),
            ("coal_mid_g_per_kwh", "中度调峰煤耗", "g/kWh"),
            ("coal_base_g_per_kwh", "基荷煤耗", "g/kWh"),
        ]
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>抽水蓄能减碳核算报告</title>
<style>
body{{font-family:"Microsoft YaHei",Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 24px;color:#10243A;line-height:1.75}}
h1{{font-size:28px;border-bottom:3px solid #2A9D8F;padding-bottom:12px}}
h2{{font-size:20px;margin-top:32px;color:#10243A}}
.kpi{{display:flex;gap:16px;margin:20px 0}}
.kpi div{{flex:1;background:#F4F7FA;border-left:4px solid #2A9D8F;padding:14px 16px}}
.kpi b{{display:block;font-size:24px;color:#2A9D8F}}
table{{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}}
th,td{{border:1px solid #D8E1EA;padding:8px 10px;text-align:right}}
th:first-child,td:first-child{{text-align:left}}
th{{background:#10243A;color:#fff}}
.note{{color:#6B7C93;font-size:13px}}
</style></head><body>
<h1>抽水蓄能减碳核算报告</h1>
<p class="note">模型版本 {html.escape(str(result.get('method_version','-')))} ｜ 核算 {s['days']} 天 ｜ 蓄能碳效参谋</p>
<div class="kpi">
<div><span>减碳量</span><b>{_fmt(s['reduction_t'])} t</b><span>{s['reduction_10kt']:.4f} 万吨</span></div>
<div><span>减排率</span><b>{s['reduction_rate_pct']:.2f}%</b><span>相对无抽蓄情景</span></div>
<div><span>有抽蓄排放</span><b>{_fmt(s['emissions_with_phs_kg']/1e3)} t</b><span>无抽蓄 {_fmt(s['emissions_without_phs_kg']/1e3)} t</span></div>
</div>
<h2>一、核算口径</h2>
<table><tr><th>参数</th><th>取值</th><th>单位</th></tr>{param_rows}</table>
<h2>二、分日结果</h2>
<table><tr><th>日期</th><th>有抽蓄排放（t）</th><th>无抽蓄排放（t）</th><th>减碳（t）</th><th>减排率</th></tr>{rows}</table>
<h2>三、假设与提示</h2>
<ul>{''.join(f'<li>{html.escape(x)}</li>' for x in result.get('assumptions', []))}</ul>
<p><b>警告：</b></p><ul>{warnings}</ul>
<h2>四、边界</h2>
<p>{html.escape(result.get('disclaimer','结果仅用于科研、教学与方案比较。'))}</p>
<hr><p class="note">本报告由蓄能碳效参谋自动生成；计算数值来自确定性核算工具。</p>
</body></html>"""


def render(result_path: Path, md_path: Path, html_path: Path | None = None) -> None:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(build_markdown(result), encoding="utf-8")
    if html_path:
        html_path.write_text(build_html(result), encoding="utf-8")
