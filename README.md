# 蓄能碳效参谋（PHS Carbon Copilot）

把《抽水蓄能减碳效益优化核算软件 V1.0》的核算能力，封装成一个**会问参数、会调工具、会解释结果**的智能体。面向抽水蓄能、火电深度调峰、新能源消纳的方案对比与科研核算。

## 30 秒跑起来

```bash
cd skills/pumped-storage-carbon
python cli.py --demo
```

预期输出：

```
减碳量：9,547.8 t  (0.9548 万吨)
减排率：2.30%
有抽蓄排放：405,702.9 t
无抽蓄排放：415,250.8 t
```

全年 365 天：

```bash
python cli.py --input examples/input_year.json --output ../../outputs/demo_year.json
```

## 已验证

| 项目 | 结果 |
|---|---|
| 与 MATLAB `AA.mat` 对比 | 365 天逐日复算，3 位小数一致（最大误差 <0.001） |
| 单日（2026-11-17） | 减碳 9,547.843 t，减排率 2.2993% |
| 全年 365 天 | 减碳 897,883.4 t = 89.7883 万吨，减排率 0.6425% |
| 自动化评测 | 20/20 通过（含缺字段、长度错、负值、参数越界等错误输入） |
| 成品文档 | 实践报告 PDF 6 页 / DOCX；答辩 PPTX 10 页 |
| 全年耗时 | 约 120 ms（普通笔记本） |
| 依赖 | Python 3.9+，核心计算仅标准库 |

## 目录

```
agent/
  system_prompt.md        智能体系统提示词（直接粘贴到平台）
  tool_schema.json        工具 JSON Schema
  platform_config.json    平台字段、工具、验收问题
  pareto_tool_schema.json
  report_tool_schema.json
  knowledge/              知识库（模型、参数、FAQ、边界）
skills/pumped-storage-carbon/
  SKILL.md                SKILL 契约
  carbon_core.py          核算核心（MATLAB 复刻）
  cli.py                  命令行入口
  http_server.py          HTTP 接入（/calculate /pareto /report）
  examples/               单日、三日、全年示例输入
skills/pareto-explorer/
  SKILL.md                Pareto 前沿查询契约
  pareto_core.py          折中解/极值/拐点
skills/carbon-report/
  SKILL.md                报告生成契约
  report_core.py          Markdown / HTML 报告
eval/
  test_cases.jsonl        20 条自动 + 5 条人工评测
  run_eval.py             评测执行器
docs/
  one_pager.md            参赛一页纸
  platform_assembly.md    平台装配步骤
  demo_script.md          3 分 30 秒分镜与逐字稿
data/raw/                 本地示例原始数据（不随作品包提交）
outputs/                  结果、图表、报告
```

## 平台装配（三步）

1. 启动工具服务：`python skills/pumped-storage-carbon/http_server.py --port 8790`
2. 新建智能体，粘贴 `agent/system_prompt.md`，上传 `agent/knowledge/` 四个文件。
3. 按 `agent/platform_config.json` 添加三个工具：
   - `carbon_calculate` → `POST /calculate`
   - `pareto_explore` → `POST /pareto`
   - `report_generate` → `POST /report`

详细步骤见 `docs/platform_assembly.md`。

## 增强能力

- **Pareto 查询**：`python skills/pareto-explorer/pareto_cli.py -i skills/pareto-explorer/examples/pareto_day321.json`
- **报告生成**：`python skills/carbon-report/report_cli.py -i outputs/demo_day.json -o outputs/report_day.md --html outputs/report_day.html`
- **参数敏感性**：`python scripts/sensitivity.py && python scripts/make_figures.py`

## 当前状态

已完成：核算核心、Pareto 查询、报告生成、提示词、知识库、工具 Schema、HTTP 服务、20 项评测、示例数据、敏感性分析、三张图表、平台配置、Demo 脚本、一页纸；实践报告 PDF（6 页）/DOCX 与答辩 PPTX（10 页）。

待完成：

- 在 SCNet 智能体平台创建并发布智能体（当前运行时无创建工具，需客户端界面操作）；
- 申请活动算力或充值后提交真实作业（账号余额 0，Agent1 队列排队）；
- 报名、团队/导师授权。

## 数据与合规

- 示例数据仅用于演示，不代表任何真实电站。
- `data/raw/` 与 `data/local/` 不随作品包提交。
- 模型口径与软著一致；引用请注明软著登记号 `2026R11L3004891`。
- 输出仅用于科研、教学与方案比较，不构成调度指令或 CCER 签发依据。
