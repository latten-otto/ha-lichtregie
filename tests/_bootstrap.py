"""Macht die Module ohne Home Assistant importierbar.

``custom_components/lichtregie/__init__.py`` importiert Home Assistant. Für
die Tests der reinen Logik wird das Paket deshalb von Hand registriert,
ohne seine ``__init__`` auszuführen. Die relativen Importe innerhalb des
Pakets funktionieren dadurch weiter.
"""

from __future__ import annotations

import os
import sys
import types

ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "custom_components", "lichtregie")
)

if "lichtregie" not in sys.modules:
    package = types.ModuleType("lichtregie")
    package.__path__ = [ROOT]
    sys.modules["lichtregie"] = package

    for sub in ("core", "link", "api"):
        module = types.ModuleType(f"lichtregie.{sub}")
        module.__path__ = [os.path.join(ROOT, sub)]
        sys.modules[f"lichtregie.{sub}"] = module


def run(namespace: dict) -> int:
    """Führt alle Testfunktionen eines Moduls aus."""
    failed = 0
    for name, fn in sorted(namespace.items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok   {name}")
            except AssertionError as err:
                failed += 1
                print(f"  FAIL {name}: {err}")
            except Exception as err:  # noqa: BLE001
                failed += 1
                print(f"  KAPUTT {name}: {type(err).__name__}: {err}")
    print("  →", "alle Tests bestanden" if not failed else f"{failed} fehlgeschlagen")
    return 1 if failed else 0
