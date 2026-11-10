#!/usr/bin/env python3
"""报告生成 SKILL 命令行。"""

from __future__ import annotations

import argparse
from pathlib import Path

from report_core import render


def main() -> int:
    parser = argparse.ArgumentParser(description="把核算结果 JSON 转成 Markdown / HTML 报告")
    parser.add_argument("-i", "--input", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--html", type=Path)
    args = parser.parse_args()
    render(args.input, args.output, args.html)
    print(f"已生成：{args.output}" + (f"；{args.html}" if args.html else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
