"""Verifies, from inside the app, that it is cut off from the network: the
counterpart of the macOS edition's IsolationChecker.

On macOS the App Sandbox denies sockets, which a live probe shows. A Flatpak
without --share=network instead runs in a network namespace of its own that
has only the loopback interface: there is no route off the computer at all.
So the check reads the sandbox's own description (/.flatpak-info) and lists
the network interfaces the app can see (/sys/class/net). Nothing here opens a
socket, so the check itself never touches the network.
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, field

FLATPAK_INFO = "/.flatpak-info"
NET_CLASS = "/sys/class/net"


@dataclass
class IsolationReport:
    sandboxed: bool = False
    app_id: str = ""
    network_permission: bool = False
    filesystems: list[str] = field(default_factory=list)
    interfaces: list[str] = field(default_factory=list)

    @property
    def only_loopback(self) -> bool:
        return all(i == "lo" for i in self.interfaces)

    @property
    def is_isolated(self) -> bool:
        """True when the sandbox guarantees the app cannot open network connections."""
        return self.sandboxed and not self.network_permission and self.only_loopback

    @property
    def interfaces_text(self) -> str:
        return ", ".join(self.interfaces) if self.interfaces else "none"


def report(info_path: str = FLATPAK_INFO, net_path: str = NET_CLASS) -> IsolationReport:
    r = IsolationReport()
    if os.path.isfile(info_path):
        r.sandboxed = True
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            cp.read(info_path, encoding="utf-8")
        except (configparser.Error, OSError, UnicodeDecodeError):
            pass
        r.app_id = cp.get("Application", "name", fallback="")
        shared = [s for s in cp.get("Context", "shared", fallback="").split(";") if s]
        r.network_permission = "network" in shared
        r.filesystems = [s for s in cp.get("Context", "filesystems", fallback="").split(";") if s]
    try:
        r.interfaces = sorted(os.listdir(net_path))
    except OSError:
        r.interfaces = []
    return r
