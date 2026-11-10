#!/usr/bin/env python3
"""生成报告与 PPT 用的三张图：敏感性、典型日调度、系统架构。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

fm.fontManager.addfont(r"C:\Windows\Fonts\msyh.ttc")
plt.rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False

NAVY = "#10243A"
TEAL = "#2A9D8F"
AMBER = "#E9C46A"
GREY = "#6B7C93"
LIGHT = "#F4F7FA"

SENS = OUT / "sensitivity.csv"
DAY_IN = ROOT / "skills" / "pumped-storage-carbon" / "examples" / "input_day.json"
DAY_OUT = OUT / "demo_day.json"


def fig_sensitivity() -> None:
    rows = list(csv.DictReader(SENS.open(encoding="utf-8-sig")))
    groups = {
        "zpump_mw": ("抽蓄装机（MW）", [700, 1000, 1400, 1800, 2100]),
        "efficiency": ("抽放综合效率", [0.70, 0.75, 0.80]),
        "min_load_ratio": ("最小出力比例（死区）", [0.10, 0.20, 0.30]),
    }
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.2), dpi=200)
    for ax, (key, (label, order)) in zip(axes, groups.items()):
        data = {float(r["value"]): float(r["annual_reduction_10kt"]) for r in rows if r["parameter"] == key}
        xs = order
        ys = [data[x] for x in xs]
        ax.plot(xs, ys, color=TEAL, marker="o", linewidth=2.4, markersize=6, zorder=3)
        base_x = 1400 if key == "zpump_mw" else (0.75 if key == "efficiency" else 0.20)
        base_y = data[base_x]
        ax.scatter([base_x], [base_y], s=110, color=AMBER, edgecolor=NAVY, zorder=4, label="原优化点")
        ax.axhline(base_y, color=GREY, linestyle="--", linewidth=1, alpha=0.6)
        for x, y in zip(xs, ys):
            ax.annotate(f"{y:.1f}", (x, y), textcoords="offset points", xytext=(0, 9),
                        ha="center", fontsize=9, color=NAVY)
        ax.set_xlabel(label, fontsize=11, color=NAVY)
        ax.set_ylabel("年减碳量（万吨）", fontsize=11, color=NAVY)
        ax.set_title(label, fontsize=13, color=NAVY, pad=10)
        ax.grid(axis="y", linestyle=":", alpha=0.45)
        ax.set_facecolor(LIGHT)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
    fig.suptitle("参数敏感性：固定 NSGA-II 调度轨迹，仅改变单一参数（非重优化）",
                 fontsize=14, color=NAVY, y=1.02)
    fig.text(0.5, -0.02, "注：原优化点为 1400 MW / 0.75 / 0.20；偏离后结果下降，说明调度轨迹与参数强耦合，实际配置需联动重优化。",
             ha="center", fontsize=9.5, color=GREY)
    fig.tight_layout()
    path = OUT / "fig_sensitivity.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("已生成", path)


def fig_daily() -> None:
    inp = json.loads(DAY_IN.read_text(encoding="utf-8"))["days"][0]
    res = json.loads(DAY_OUT.read_text(encoding="utf-8"))["days"][0]
    hours = list(range(24))
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6.4), dpi=200, sharex=True,
                                   gridspec_kw={"height_ratios": [2.2, 1.2]})
    without_hourly = [h["thermal_mw"] for h in res["without_phs"]["hourly"]]
    ax1.plot(hours, without_hourly, color=GREY, linewidth=2.2, label="无抽蓄火电出力")
    ax1.plot(hours, [h["thermal_mw"] for h in res["with_phs"]["hourly"]],
             color=TEAL, linewidth=2.4, label="有抽蓄火电出力")
    ax1.fill_between(hours,
                     [h["thermal_mw"] for h in res["with_phs"]["hourly"]],
                     [h["thermal_mw"] for h in res["without_phs"]["hourly"]],
                     color=AMBER, alpha=0.25, label="削峰空间")
    ax1.set_ylabel("火电出力（MW）", fontsize=11, color=NAVY)
    ax1.set_title("2026-11-17 典型日：抽蓄削峰填谷，减碳 9,547.8 t（减排率 2.30%）",
                  fontsize=13, color=NAVY, pad=10)
    ax1.legend(loc="upper left", frameon=False, fontsize=10)
    ax1.grid(axis="y", linestyle=":", alpha=0.45)
    ax1.set_facecolor(LIGHT)
    for spine in ("top", "right"):
        ax1.spines[spine].set_visible(False)

    npump = res["npump_mw"]
    colors = [TEAL if v >= 0 else "#D97757" for v in npump]
    ax2.bar(hours, npump, color=colors, width=0.72)
    ax2.axhline(0, color=NAVY, linewidth=0.9)
    ax2.set_ylabel("抽蓄功率（MW）", fontsize=11, color=NAVY)
    ax2.set_xlabel("时刻（h）", fontsize=11, color=NAVY)
    ax2.set_xticks(hours)
    ax2.tick_params(axis="x", labelsize=8)
    ax2.text(0.01, 0.92, "正=发电，负=抽水", transform=ax2.transAxes, fontsize=9, color=GREY)
    ax2.grid(axis="y", linestyle=":", alpha=0.45)
    ax2.set_facecolor(LIGHT)
    for spine in ("top", "right"):
        ax2.spines[spine].set_visible(False)
    fig.tight_layout()
    path = OUT / "fig_daily.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("已生成", path)


def box(ax, x, y, w, h, text, fc, ec, fs=12, tc="white", bold=False):
    patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                           facecolor=fc, edgecolor=ec, linewidth=1.4)
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=tc, fontweight="bold" if bold else "normal", wrap=True)


def arrow(ax, x1, y1, x2, y2, color=GREY):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=14, linewidth=1.5, color=color))


def fig_architecture() -> None:
    fig, ax = plt.subplots(figsize=(12, 6.4), dpi=200)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    box(ax, 0.03, 0.62, 0.18, 0.18, "用户\n教师 / 研究生 / 电站前期", NAVY, NAVY, 11)
    box(ax, 0.30, 0.58, 0.24, 0.26, "智能体\n意图识别 · 参数追问\n结果解释 · 报告生成", TEAL, TEAL, 11, bold=True)
    box(ax, 0.30, 0.20, 0.24, 0.20, "知识库\n模型公式 / 参数口径\nFAQ / 边界", "#FFFFFF", TEAL, 10.5, tc=NAVY)
    box(ax, 0.65, 0.62, 0.30, 0.18, "工具层\n核算 SKILL · Pareto 查询 · 报告生成", AMBER, "#B98B2E", 11, tc=NAVY)
    box(ax, 0.65, 0.20, 0.30, 0.20, "输出\n逐时功率 / 减碳量 / 减排率\n结构化报告", "#FFFFFF", GREY, 10.5, tc=NAVY)

    arrow(ax, 0.21, 0.71, 0.30, 0.71)
    arrow(ax, 0.42, 0.58, 0.42, 0.40, color=TEAL)
    arrow(ax, 0.54, 0.71, 0.65, 0.71)
    arrow(ax, 0.80, 0.62, 0.80, 0.40, color=GREY)

    ax.text(0.5, 0.94, "蓄能碳效参谋：系统架构", ha="center", fontsize=18, color=NAVY, fontweight="bold")
    ax.text(0.5, 0.08, "一次核算 = 参数校验 → 调用工具 → 结果解释；知识库只提供口径，不替代计算。",
            ha="center", fontsize=10, color=GREY)
    fig.tight_layout()
    path = OUT / "fig_architecture.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("已生成", path)


if __name__ == "__main__":
    fig_sensitivity()
    fig_daily()
    fig_architecture()
