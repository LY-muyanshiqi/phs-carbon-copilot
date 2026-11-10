---
name: carbon-report
description: 把抽水蓄能减碳核算结果 JSON 转成结构化 Markdown / HTML 报告，包含结论、核算口径、分日结果、假设与边界。
---

# 碳核算报告生成 SKILL

## 何时使用

- 用户已经拿到核算结果 JSON，需要一份可读的报告；
- 需要把结果贴进实践报告、课程作业或评审材料；
- 需要统一口径，避免每次手写结论。

不适用：还没有核算结果。先调用 `pumped-storage-carbon`。

## 输入

`pumped-storage-carbon` 的输出 JSON（`ok: true`），例如 `outputs/demo_day.json`。

## 输出

- Markdown：适合粘贴、版本管理；
- HTML：适合打印/截图，内置简洁样式。

报告结构：

1. 结论（减碳量、减排率、两种情景排放）
2. 核算口径（9 个参数）
3. 分日结果表
4. 假设与警告
5. 边界与免责声明

## 调用

```bash
python report_cli.py -i ../../outputs/demo_day.json -o ../../outputs/report_day.md --html ../../outputs/report_day.html
```

## 规则

- 只读取结果 JSON，不重新计算；数值以结果文件为准。
- 负减碳量照实写出，不改成绝对值。
- 警告必须保留，不能为了报告好看而删掉。
- 报告末尾保留“自动生成”标识，便于 AIGC 标识与追溯。
