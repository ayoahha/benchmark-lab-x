#!/usr/bin/env python3

from pathlib import Path
import os
import sys


CORE = Path(__file__).resolve().with_name("shared_acquisition.py")


if __name__ == "__main__":
    os.execv(
        "/opt/homebrew/bin/python3",
        ["python3", str(CORE), *sys.argv[1:], "--path", "manual"],
    )
