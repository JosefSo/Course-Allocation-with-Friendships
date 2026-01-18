#!/usr/bin/env python3
"""
CLI entrypoint wrapper for the HBS social draft implementation.
"""

from __future__ import annotations

from HBS.hbs_api import run_hbs_social
from HBS.hbs_cli import main

__all__ = ["run_hbs_social"]


if __name__ == "__main__":
    raise SystemExit(main())
