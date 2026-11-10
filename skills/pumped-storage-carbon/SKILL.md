---
name: pumped-storage-carbon
description: 抽水蓄能—火电深度调峰协同减碳核算。输入逐时负荷、水/风/光出力和抽蓄参数，输出有/无抽蓄两种情景的 CO2 排放、减碳量、减排率与逐时明细。用于方案对比、参数敏感性、全年 8760 小时核算。
---

# 抽水蓄能减碳核算 SKILL

## 1. 何时使用

出现以下任务时调用：

- “某抽蓄电站一年能减多少碳？”
- “1400 MW / 4 h 抽蓄，效率 0.75，帮我算一下。”
- “有无抽蓄两种方案对比。”
- “装机/效率/死区变化对减碳量有什么影响？”
- “把这份 365 天负荷与风光数据跑一遍。”

不适用：实时调度、机组控制、机电暂态、CCER 签发、投资决策。

## 2. 输入

```json
{
  "project": "项目名（可选）",
  "params": {
    "zpump_mw": 1400,
    "duration_h": 4,
    "efficiency": 0.75,
    "min_load_ratio": 0.2,
    "oxidation_factor": 0.99,
    "carbon_content": 0.7,
    "coal_deep_g_per_kwh": 370,
    "coal_mid_g_per_kwh": 330,
    "coal_base_g_per_kwh": 300
  },
  "days": [
    {
      "date": "2026-11-17",
      "load_mw": [24 个数],
      "hydro_mw": [24 个数],
      "wind_mw": [24 个数],
      "solar_mw": [24 个数],
      "soc": [25 个数，可选]
    }
  ]
}
```

约束：

- `days` 非空；每日四个功率数组长度必须为 24，单位 MW，非负。
- `soc` 可选；给了就必须 25 点、0–1、首末 0.5。
- 参数缺省时用默认值；未知字段会被拒绝。
- 不提供 `soc` 时使用启发式调度，输出会带警告。

## 3. 输出

```json
{
  "ok": true,
  "method_version": "1.0.0",
  "summary": {
    "days": 1,
    "reduction_kg": 9547842.549,
    "reduction_t": 9547.843,
    "reduction_10kt": 0.954784,
    "reduction_rate_pct": 2.2993,
    "emissions_with_phs_kg": 405702909.64,
    "emissions_without_phs_kg": 415250752.189
  },
  "days": [
    {
      "date": "2026-11-17",
      "npump_mw": ["24 个，正=发电，负=抽水"],
      "thermal_with_phs_mw": ["24 个"],
      "thermal_without_phs_mw": ["24 个"],
      "with_phs": {"zt_f_mw": 17845.485, "nt_b_mw": 10356.129, "emissions_kg": 405702909.64, "hourly": ["..."]},
      "without_phs": {"...": "..."},
      "reduction_t": 9547.843,
      "reduction_rate_pct": 2.2993,
      "warnings": []
    }
  ],
  "assumptions": ["..."],
  "disclaimer": "..."
}
```

## 4. 调用方式

### 4.1 命令行

```bash
python cli.py --demo
python cli.py --input examples/input_day.json --output outputs/day.json
python cli.py --input examples/input_year.json --output outputs/year.json
```

### 4.2 HTTP（推荐给智能体平台）

```bash
python http_server.py --port 8790
```

- `GET /health` → `{"ok": true, "method_version": "1.0.0"}`
- `POST /calculate`，body 为上面的输入 JSON，返回结果 JSON。
- 错误时 HTTP 422，body 为 `{"ok": false, "error": {"code": "...", "message": "...", "field": "..."}}`。

### 4.3 Python

```python
from carbon_core import evaluate_payload
result = evaluate_payload(payload)
```

## 5. 错误码

| 代码 | 含义 | 处理 |
|---|---|---|
| `E_LENGTH` | 数组长度不是 24（SOC 不是 25） | 补齐/截断到规定长度 |
| `E_RANGE` | 负值、SOC 越界、参数超范围 | 检查数据与参数 |
| `E_PARAM` | 参数越界（如 zpump=0、效率>1） | 按建议范围修正 |
| `E_INPUT` | 字段缺失、类型错误、未知参数 | 按 schema 修正 |
| `E_JSON` | 请求体不是合法 JSON | 检查格式 |
| `E_INTERNAL` | 服务端未预期错误 | 保留请求体，联系开发者 |

## 6. 示例

```bash
cd skills/pumped-storage-carbon
python cli.py --demo
```

输出摘要：

```
减碳量：9,547.8 t  (0.9548 万吨)
减排率：2.30%
有抽蓄排放：405,702.9 t
无抽蓄排放：415,250.8 t
```

## 7. 校验基线

- 与 `AA.mat` 中 365 天逐日复算：3 位小数一致（最大误差 <0.001）；6 个样本日列出。
- 全年 365 天：897,883.4 t = 89.7883 万吨，减排率 0.6425%；
- 运行环境：Python 3.9+，仅依赖标准库（核心计算不需要 numpy）。
- 全年 365 天在普通笔记本上 < 1 s。

## 8. 版本与许可

- 版本：`1.0.0`
- 模型口径：《抽水蓄能减碳效益优化核算软件 V1.0》，著作权人李垚，软著登记号 `2026R11L3004891`
- 仅用于科研、教学与方案比较；不构成调度指令或碳资产签发依据。
