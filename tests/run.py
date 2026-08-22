"""Führt alle Testdateien aus."""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    failed, passed = 0, 0
    for name in sorted(os.listdir(HERE)):
        if not name.startswith("test_") or not name.endswith(".py"):
            continue
        print(f"\n=== {name} ===")
        out = subprocess.run(
            [sys.executable, os.path.join(HERE, name)], capture_output=True, text=True
        )
        sys.stdout.write(out.stdout)
        if out.stderr:
            sys.stderr.write(out.stderr)
        passed += out.stdout.count("  ok   ")
        if out.returncode:
            failed += 1
    print(f"\n{passed} Tests bestanden · {failed} Datei(en) mit Fehlern")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
