---
name: pareto-explorer
description: 读取 NSGA-II 的 Pareto 前沿点，按“均衡/低排放/低调峰”偏好选折中解，并返回两端极值点与拐点。用于回答“装机多大合适”“调峰与排放如何权衡”。
---

# Pareto 前沿查询 SKILL

## 何时使用

- 用户已有 NSGA-II 的 Pareto 解集，想知道“哪一个解最合适”；
- 需要展示“调峰深度—碳排放”的权衡关系；
- 需要回答“最低排放能到多少”“最小调峰深度是多少”。

不适用：没有前沿点、需要重新跑优化。此时先用 MATLAB/NSGA-II 生成解集。

## 输入

```json
{
  "project": "第 321 天 Pareto 前沿",
  "date": "2026-11-17",
  "preference": "balanced",
  "points": [
    {"zt_f_mw": 17845.5, "emissions_kg": 405702909.6},
    {"zt_f_mw": 15024.5, "emissions_kg": 412761063.4}
  ]
}
```

- `points` 至少 3 个；`zt_f_mw` ≥ 0，`emissions_kg` > 0。
- `preference`：`balanced`（默认）、`low_peak`（更重视调峰深度）、`low_carbon`（更重视排放）。

## 输出

```json
{
  "ok": true,
  "preference": "balanced",
  "count": 100,
  "ranges": {"zt_f_mw": [15024.5, 18611.2], "emissions_kg": [405046601.6, 412761063.4]},
  "compromise": {"zt_f_mw": 17845.5, "emissions_kg": 405702909.6, "role": "compromise"},
  "min_peak": {"zt_f_mw": 15024.5, "emissions_kg": 412761063.4, "role": "min_peak"},
  "min_carbon": {"zt_f_mw": 18611.2, "emissions_kg": 405046601.6, "role": "min_carbon"},
  "knee": {"...": "..."},
  "points": ["..."]
}
```

## 调用

```bash
python pareto_cli.py -i examples/pareto_day321.json --preference balanced -o ../../outputs/pareto.json
```

HTTP：`POST /pareto`，body 同上。

## 口径

- 归一化：对 `zt_f_mw` 与 `emissions_kg` 分别做 min-max；
- 综合得分：`(1-x_peak)*w1 + (1-x_carbon)*w2`；
- `balanced` 取 0.5/0.5，`low_peak` 取 0.8/0.2，`low_carbon` 取 0.2/0.8；
- 拐点取 `x_peak + x_carbon` 最大者，代表离两端连线最远的折中点。

## 注意

- 前沿点必须来自同一天、同一组参数、同一次优化；不同天/不同参数的点不能混在一起比较。
- 折中解不是“客观最优”，只是按偏好权重的推荐；报告中必须写明偏好。
- 若所有点都不可行（惩罚值 1e12），应先检查优化约束，而不是选点。
