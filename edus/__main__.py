"""Allow: python -m edus book|check|monitor|..."""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    cli = Path(__file__).resolve().parent.parent / "scripts" / "edus_cli.py"
    runpy.run_path(str(cli), run_name="__main__")


if __name__ == "__main__":
    main()
