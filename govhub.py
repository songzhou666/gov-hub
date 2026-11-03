# -*- coding: utf-8 -*-
"""gov-hub 入口包装：python govhub.py init|check|status --root <dir>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from govhub.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
