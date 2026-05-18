from __future__ import annotations

import os
import sys
from pathlib import Path


def configure_tcl_tk() -> None:
    if not getattr(sys, "frozen", False):
        return

    resource_root = Path(getattr(sys, "_MEIPASS"))
    tcl_root = resource_root / "tcl"
    tcl_library = tcl_root / "tcl8.6"
    tk_library = tcl_root / "tk8.6"

    if tcl_library.exists():
        os.environ.setdefault("TCL_LIBRARY", str(tcl_library))
    if tk_library.exists():
        os.environ.setdefault("TK_LIBRARY", str(tk_library))


configure_tcl_tk()

from app.desktop_host import main


if __name__ == "__main__":
    main()
