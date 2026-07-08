#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from HBS.hbs_research import run_research_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a versioned HBS research experiment")
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    result = run_research_config(args.config)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    print(
        "WARNING: combined utility must not be ranked across different lambda values."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
