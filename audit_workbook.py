#!/usr/bin/env python3
"""
Top-level entry script to run the Kestrel R&D Data Audit Suite.
Usage:
    .venv/bin/python audit_workbook.py
"""

import sys
from pathlib import Path

# Ensure src/ is in sys.path
root_dir = Path(__file__).resolve().parent
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from kestrel_audit.cli import main

if __name__ == "__main__":
    main()
