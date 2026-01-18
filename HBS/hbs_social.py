#!/usr/bin/env python3
"""
CLI entrypoint wrapper for the HBS social draft implementation.
"""

from __future__ import annotations

if __package__ is None:
    from pathlib import Path
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from HBS.hbs_api import run_hbs_social
    from HBS.hbs_cli import main
else:
    from .hbs_api import run_hbs_social
    from .hbs_cli import main

__all__ = ["run_hbs_social"]


if __name__ == "__main__":
    raise SystemExit(main())
