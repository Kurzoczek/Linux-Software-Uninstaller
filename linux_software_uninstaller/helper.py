#!/usr/bin/python3 -I
"""Linux Software Uninstaller helper, run as root through pkexec (polkit: linux-software-uninstaller.helper).

Accepts only these commands and validates every argument:
  [--lang CODE] uninstall [--snapshot] [--apt P..] [--snap S..] [--flatpak ID[@installation]..] [--opt DIR..] [--desktop FILE..]
  [--lang CODE] remove-paths PATH..
  [--lang CODE] cleanup [--autoremove] [--purge-rc P..] [--apt-clean]
"""

import os
import re
import sys
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

_here = Path(__file__).resolve().parent
_root = _here.parent if (_here / "core.py").exists() else Path("/usr/share/linux-software-uninstaller")
sys.path.insert(0, str(_root))

from linux_software_uninstaller import core, i18n  # noqa: E402
from linux_software_uninstaller.i18n import tr, n_  # noqa: E402

PKG_RE = re.compile(r"^[a-z0-9][a-z0-9+.\-]+(:[a-z0-9\-]+)?$")
SNAP_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")
FLATPAK_RE = re.compile(r"^[A-Za-z0-9_\-]+(\.[A-Za-z0-9_\-]+){2,}$")
INST_RE = re.compile(r"^[A-Za-z0-9_\-]+$")

ENV = dict(os.environ, DEBIAN_FRONTEND="noninteractive", LC_ALL="C.UTF-8", LANG="C.UTF-8")


def say(msg):
    print(msg, flush=True)


def call(cmd):
    say("$ " + " ".join(cmd))
    try:
        return subprocess.call(cmd, env=ENV)
    except OSError as e:
        say(f"!! {e}")
        return 1


def fail(msg):
    say(tr("!! Rejected: {msg}", msg=msg))
    sys.exit(2)


def check(values, regex, what):
    for v in values:
        if not regex.match(v):
            fail(tr("invalid name ({what}): {v}", what=tr(what), v=repr(v)))


def config_backup(apt, others):
    """Backup that works on any file system: package list, their configuration files and a restore script."""
    stamp = f"{datetime.now():%Y-%m-%d_%H%M%S}"
    d = core.BACKUP_DIR / stamp
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(core.BACKUP_DIR, 0o700)
    say(tr("» Configuration backup → {d}", d=d))
    if apt:
        lines = [ln for ln in core.out(["dpkg-query", "-W", "-f", "${binary:Package}=${Version}\n", *apt]).splitlines()
                 if not ln.endswith("=")]
        (d / "packages.txt").write_text("\n".join(lines) + "\n")
        files = set()
        for line in core.out(["dpkg-query", "-W", "-f", "${Conffiles}\n", *apt]).splitlines():
            line = line.strip()
            if line.startswith("/"):
                files.add(line.split()[0])
        files = sorted(f for f in files if os.path.isfile(f))
        if files:
            call(["tar", "-czf", str(d / "config.tar.gz"), "-C", "/", *[f.lstrip("/") for f in files]])
        say(tr("  saved {packages} and {files}", packages=n_(len(lines), "package"), files=n_(len(files), "conffile")))
    if others:
        (d / "other.txt").write_text("\n".join(others) + "\n")
    script = d / "restore.sh"
    script.write_text(
        "#!/bin/sh\n# Restores packages removed by Linux Software Uninstaller: sudo sh restore.sh\nset -e\n"
        'cd "$(dirname "$0")"\n'
        '[ -s packages.txt ] && apt-get install -y $(cut -d= -f1 packages.txt)\n'
        "[ -f config.tar.gz ] && tar -xzf config.tar.gz -C /\n"
        '[ -s other.txt ] && echo "Also reinstall manually:" && cat other.txt\n'
        "echo Done.\n")
    script.chmod(0o755)
    old = sorted(p for p in core.BACKUP_DIR.iterdir() if p.is_dir())
    for p in old[:-20]:          # keep the 20 newest backups
        call(["rm", "-rf", "--one-file-system", "--", str(p)])
    say(tr("✓ Backup ready."))


def backup(apt, others):
    method = core.backup_method()
    if method == "snapper":
        say(tr("» Creating a snapper snapshot…"))
        if call(["snapper", "-c", "root", "create", "-d", "Linux Software Uninstaller: before uninstall"]) == 0:
            return say(tr("✓ Snapshot ready."))
    elif method == "btrfs":
        say(tr("» Creating a btrfs snapshot…"))
        os.makedirs("/.snapshots", exist_ok=True)
        if call(["btrfs", "subvolume", "snapshot", "-r", "/",
                 f"/.snapshots/lsu-{datetime.now():%Y%m%d-%H%M%S}"]) == 0:
            return say(tr("✓ Snapshot ready."))
    elif method == "timeshift":
        say(tr("» Creating a Timeshift restore point (this may take a few minutes)…"))
        if call(["timeshift", "--create", "--scripted", "--comments", "Linux Software Uninstaller: before uninstall"]) == 0:
            return say(tr("✓ Restore point ready."))
    if method != "config":
        say(tr("!! The full backup failed — saving at least the package configuration."))
    try:
        config_backup(apt, others)
    except OSError as e:
        say(tr("!! Backup failed: {e} — continuing.", e=e))


def cmd_uninstall(a):
    check(a.apt, PKG_RE, "package")
    check(a.snap, SNAP_RE, "snap")
    flatpaks = []
    for f in a.flatpak:
        app_id, _, inst = f.partition("@")
        check([app_id], FLATPAK_RE, "flatpak")
        if inst and not INST_RE.match(inst):
            fail(tr("invalid Flatpak installation: {v}", v=repr(inst)))
        flatpaks.append((app_id, inst or "system"))
    opts = []
    for d in a.opt:
        p = os.path.realpath(d)
        if os.path.dirname(p) != "/opt" or os.path.islink(d) or not os.path.isdir(p):
            fail(tr("not a folder in /opt: {p}", p=d))
        opts.append(p)
    desktops = []
    for d in a.desktop:
        p = os.path.normpath(d)
        if (os.path.dirname(p) not in ("/usr/share/applications", "/usr/local/share/applications")
                or not p.endswith(".desktop")):
            fail(tr("menu entry not allowed: {p}", p=d))
        desktops.append(p)
    owned = core.dpkg_owned(opts + desktops) if opts or desktops else set()
    if owned:
        fail(tr("paths belong to packages: {p}", p=", ".join(sorted(owned))))

    status = 0
    if a.snapshot:
        backup(a.apt, a.snap + [f for f, _ in flatpaks] + opts)
    if a.apt:
        say(tr("» Uninstalling APT packages…"))
        status |= call(["apt-get", "purge", "-y", *a.apt]) != 0
    for s in a.snap:
        say(tr("» Removing snap {s}…", s=s))
        status |= call(["snap", "remove", "--purge", s]) != 0
    for app_id, inst in flatpaks:
        say(tr("» Removing Flatpak {s}…", s=app_id))
        where = "--system" if inst == "system" else f"--installation={inst}"
        status |= call(["flatpak", "uninstall", where, "-y", "--noninteractive", "--delete-data", app_id]) != 0
    for p in opts + desktops:
        say(tr("» Removing {p}…", p=p))
        status |= call(["rm", "-rf", "--one-file-system", "--", p]) != 0
    return 1 if status else 0


def cmd_remove_paths(a):
    paths = [os.path.normpath(p) for p in a.paths]
    for p in paths:
        if not core.is_safe(p, system_only=True):
            fail(tr("unsafe path: {p}", p=p))
    owned = core.dpkg_owned(paths)
    if owned:
        fail(tr("paths belong to packages: {p}", p=", ".join(sorted(owned))))
    return 1 if call(["rm", "-rf", "--one-file-system", "--", *paths]) else 0


def cmd_cleanup(a):
    check(a.purge_rc, PKG_RE, "package")
    status = 0
    if a.autoremove:
        say(tr("» Removing orphaned dependencies…"))
        status |= call(["apt-get", "autoremove", "--purge", "-y"]) != 0
    if a.purge_rc:
        say(tr("» Purging leftover configuration…"))
        status |= call(["dpkg", "--purge", *a.purge_rc]) != 0
    if a.apt_clean:
        say(tr("» Cleaning the APT cache…"))
        status |= call(["apt-get", "clean"]) != 0
    return 1 if status else 0


def main():
    if os.geteuid() != 0:
        print("This program is started by Linux Software Uninstaller through pkexec.", file=sys.stderr)
        return 1
    ap = argparse.ArgumentParser(prog="lsu-helper")
    ap.add_argument("--lang", default="en")
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("uninstall")
    u.add_argument("--snapshot", action="store_true")
    for opt in ("apt", "snap", "flatpak", "opt", "desktop"):
        u.add_argument(f"--{opt}", nargs="+", default=[])
    r = sub.add_parser("remove-paths")
    r.add_argument("paths", nargs="+")
    c = sub.add_parser("cleanup")
    c.add_argument("--autoremove", action="store_true")
    c.add_argument("--purge-rc", nargs="+", default=[])
    c.add_argument("--apt-clean", action="store_true")
    a = ap.parse_args()
    i18n.set_language(a.lang)
    return {"uninstall": cmd_uninstall, "remove-paths": cmd_remove_paths, "cleanup": cmd_cleanup}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
