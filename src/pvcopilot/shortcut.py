"""Create a double-click launcher for the local web UI.

    pvcopilot shortcut            # on the Desktop
    pvcopilot shortcut --dir .    # somewhere else

macOS   PV-Copilot.command   (opens a Terminal window that runs the server and
                              opens the browser; close the window to stop)
Windows PV-Copilot.bat
Linux   PV-Copilot.desktop + PV-Copilot.sh

The launcher calls the Python that pvcopilot is installed in, so it keeps
working without activating the environment first.
"""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path


def default_dir() -> Path:
    d = Path.home() / "Desktop"
    return d if d.is_dir() else Path.home()


def create_shortcut(folder=None) -> list[str]:
    folder = Path(folder).expanduser() if folder else default_dir()
    folder.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    made = []
    if sys.platform == "darwin":
        p = folder / "PV-Copilot.command"
        p.write_text(
            "#!/bin/bash\n"
            "# PV-Copilot (offline local version). Close this window to stop the server.\n"
            f'exec "{py}" -m pvcopilot ui "$@"\n', encoding="utf-8")
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        made.append(str(p))
    elif os.name == "nt":
        p = folder / "PV-Copilot.bat"
        p.write_text(
            "@echo off\r\n"
            "title PV-Copilot (offline local version) - close this window to stop\r\n"
            f'"{py}" -m pvcopilot ui %*\r\n'
            "pause\r\n", encoding="utf-8")
        made.append(str(p))
    else:
        sh = folder / "PV-Copilot.sh"
        sh.write_text(f'#!/bin/sh\nexec "{py}" -m pvcopilot ui "$@"\n', encoding="utf-8")
        sh.chmod(sh.stat().st_mode | stat.S_IXUSR)
        desk = folder / "PV-Copilot.desktop"
        icon = Path(__file__).parent / "app" / "assets" / "pvcopilot_logo.png"
        desk.write_text(
            "[Desktop Entry]\nType=Application\nName=PV-Copilot (offline)\n"
            f"Exec={sh}\nIcon={icon}\nTerminal=true\n", encoding="utf-8")
        desk.chmod(desk.stat().st_mode | stat.S_IXUSR)
        made += [str(desk), str(sh)]
    return made
