"""Linux Software Uninstaller logic — no Qt; used by the interface and by the root helper."""

import os
import re
import sys
import glob
import gzip
import shlex
import shutil
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field

from .i18n import tr
from . import i18n

HOME = Path.home()
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", str(HOME / ".local/state"))) / "linux-software-uninstaller"
LOG_FILE = STATE_DIR / "activity.log"
ENV_C = dict(os.environ, LC_ALL="C.UTF-8", LANG="C.UTF-8")

INSTALLED_HELPER = Path("/usr/libexec/linux-software-uninstaller/lsu-helper")
INSTALLED_PKG_DIR = Path("/usr/share/linux-software-uninstaller")

KIND_LABEL = {"apt": "APT", "flatpak": "Flatpak", "snap": "Snap", "appimage": "AppImage", "opt": "/opt"}
KIND_LONG = {"apt": "APT package (.deb)", "flatpak": "Flatpak", "snap": "Snap",
             "appimage": "AppImage", "opt": "Manually in /opt"}
KIND_ICON = {"apt": "package-x-generic", "flatpak": "flatpak-discover", "snap": "package-x-generic",
             "appimage": "application-x-executable", "opt": "folder"}

CRITICAL = {
    "apt", "dpkg", "sudo", "systemd", "systemd-sysv", "init", "libc6", "bash", "coreutils",
    "login", "passwd", "dbus", "dbus-daemon", "polkitd", "pkexec", "policykit-1",
    "python3", "python3-pyqt6", "network-manager", "plasma-nm", "plasma-desktop",
    "plasma-workspace", "kde-plasma-desktop", "kde-standard", "kde-full", "task-kde-desktop",
    "task-desktop", "sddm", "kwin-x11", "kwin-wayland", "xserver-xorg-core", "xwayland",
    "pipewire", "wireplumber", "pipewire-pulse", "grub-efi-amd64", "grub-efi-amd64-signed",
    "grub-pc", "grub-common", "shim-signed", "linux-image-amd64", "firmware-linux",
    "btrfs-progs", "e2fsprogs", "dolphin", "konsole", "systemd-boot", "dracut", "initramfs-tools",
}
HIDDEN_SECTIONS = {"libs", "oldlibs", "libdevel", "kernel", "localization", "doc", "fonts", "metapackages"}

APT_SUFFIXES = ("-stable", "-beta", "-dev", "-bin", "-git", "-nightly", "-desktop", "-gtk",
                "-qt", "-qt5", "-qt6", "-common", "-data", "-esr", "-browser", "-client")

GENERIC = {
    "desktop", "common", "data", "gnome", "kde", "plasma", "qt", "qt5", "qt6", "gtk", "linux",
    "python", "python3", "org", "com", "net", "app", "apps", "lib", "bin", "share", "config",
    "cache", "local", "default", "system", "user", "tools", "utils", "core", "base", "theme",
    "themes", "fonts", "icons", "sound", "audio", "video", "image", "music", "files", "file",
    "terminal", "editor", "player", "browser", "settings", "office", "viewer", "monitor",
    "manager", "calculator", "mozilla", "google", "microsoft", "debian", "ubuntu", "stable",
    "client", "server", "service", "studio", "the", "and", "for", "x86_64", "amd64",
}

PROTECTED_PATHS = {str(HOME / p) for p in (
    ".config", ".local", ".local/share", ".local/state", ".local/bin", ".cache", ".var",
    ".var/app", ".ssh", ".gnupg", ".pki", ".local/share/applications", ".config/autostart",
    ".local/share/Trash", ".config/systemd", ".config/systemd/user", ".local/share/flatpak",
    ".local/share/icons", ".local/share/fonts", ".local/share/kwalletd", ".config/kdeglobals",
    ".config/plasma-org.kde.plasma.desktop-appletsrc", ".config/kwinrc", ".bashrc", ".profile",
    ".bash_profile", ".bash_history", ".Xauthority", ".mozilla", ".thunderbird",
)} | {str(HOME)}

PROTECTED_SYS_NAMES = {
    "apt", "dpkg", "systemd", "flatpak", "snapd", "ssl", "security", "pam.d", "sudoers.d",
    "polkit-1", "dbus-1", "xdg", "default", "alternatives", "X11", "fonts", "skel",
    "NetworkManager", "network", "grub.d", "udev", "modprobe.d", "sysctl.d", "ld.so.conf.d",
    "PackageKit", "debconf", "man", "journal", "private", "ucf", "sddm", "kernel", "initramfs-tools",
    "dracut.conf.d", "fstab", "passwd", "shadow", "group", "sudoers", "hosts", "resolv.conf",
    "linux-software-uninstaller",
}

DESKTOP_DIRS = [Path("/usr/share/applications"), Path("/usr/local/share/applications"),
                HOME / ".local/share/applications",
                HOME / ".local/share/flatpak/exports/share/applications",
                Path("/var/lib/flatpak/exports/share/applications"),
                Path("/var/lib/snapd/desktop/applications")]

APPIMAGE_DIRS = [HOME / "Applications", HOME / "AppImages", HOME / "Aplikacje", HOME / "Programy",
                 HOME / ".local/bin", HOME / "bin", HOME / "Pobrane", HOME / "Downloads",
                 HOME / "Pulpit", HOME / "Desktop", Path("/opt")]


# ───────────────────────────── utilities ─────────────────────────────

def run(cmd, timeout=300):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=ENV_C)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.SubprocessError) as e:
        return -1, "", str(e)


def out(cmd, timeout=300):
    return run(cmd, timeout)[1]


def have(prog):
    return shutil.which(prog) is not None


def human(n):
    if not n:
        return "—"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            if unit == "B":
                return f"{n:.0f} {unit}"
            txt = f"{n:.1f} {unit}"
            return txt.replace(".", ",") if i18n.LANG == "pl" else txt
        n /= 1024


def fmt_date(ts):
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts).strftime("%d.%m.%Y" if i18n.LANG == "pl" else "%Y-%m-%d")


def parse_hsize(s):
    m = re.search(r"([\d.,]+)\s*([kKMGT]?)i?B", s or "")
    if not m:
        return 0
    try:
        num = float(m.group(1).replace(",", "."))
    except ValueError:
        return 0
    return int(num * {"": 1, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12}[m.group(2)])


def path_size(p):
    try:
        if os.path.islink(p) or not os.path.isdir(p):
            return os.lstat(p).st_size
    except OSError:
        return 0
    total = 0
    for root, _dirs, files in os.walk(p, onerror=lambda e: None):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total


def mtime(p):
    try:
        return os.lstat(p).st_mtime
    except OSError:
        return 0


def log(msg):
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}\n")
    except OSError:
        pass


def parse_desktop(path):
    data, section = {}, None
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("["):
                    section = line
                    continue
                if section == "[Desktop Entry]" and "=" in line:
                    k, v = line.split("=", 1)
                    data.setdefault(k.strip(), v.strip())
    except OSError:
        return None
    if not data or data.get("Type", "Application") != "Application":
        return None
    return {
        "name": data.get("Name[pl]") or data.get("Name") or Path(path).stem,
        "comment": data.get("Comment[pl]") or data.get("GenericName[pl]") or data.get("Comment") or "",
        "icon": data.get("Icon", ""),
        "exec": data.get("Exec", ""),
        "hidden": data.get("NoDisplay", "").lower() == "true" or data.get("Hidden", "").lower() == "true",
        "path": str(path),
    }


def exec_basename(exec_line):
    try:
        parts = shlex.split(exec_line)
    except ValueError:
        parts = exec_line.split()
    parts = [p for p in parts if p != "env" and "=" not in p]
    return os.path.basename(parts[0]) if parts else ""


def all_desktops():
    res = []
    for d in DESKTOP_DIRS:
        for f in glob.glob(str(d / "*.desktop")):
            info = parse_desktop(f)
            if info:
                res.append(info)
    return res


def dpkg_owned(paths):
    owned = set()
    paths = list(paths)
    for i in range(0, len(paths), 150):
        _rc, o, _e = run(["dpkg-query", "-S", *paths[i:i + 150]])
        for line in o.splitlines():
            if line.startswith("diversion") or ": /" not in line:
                continue
            owned.add("/" + line.split(": /", 1)[1].strip())
    return owned


BACKUP_DIR = Path("/var/backups/linux-software-uninstaller")


def root_fs_is_btrfs():
    return out(["findmnt", "-no", "FSTYPE", "/"]).strip() == "btrfs" and have("btrfs")


def backup_method():
    """How to protect the system before uninstalling:
    snapper / btrfs — full snapshot (btrfs only),
    timeshift — Timeshift restore point (ext4 etc., if configured),
    config — on any file system: package list + their configuration files from /etc."""
    btrfs = root_fs_is_btrfs()
    if btrfs and have("snapper"):
        rc, o, _e = run(["snapper", "list-configs"], timeout=20)
        if rc == 0 and re.search(r"^\s*root\s", o, re.M):
            return "snapper"
    if btrfs:
        return "btrfs"
    if have("timeshift"):
        return "timeshift"
    return "config"


BACKUP_TEXT = {
    "snapper": "A snapper snapshot will be created before uninstalling — the whole system can be restored.",
    "btrfs": "A btrfs snapshot will be created in /.snapshots before uninstalling — the whole system can be restored.",
    "timeshift": "A Timeshift restore point will be created before uninstalling.",
    "config": "Before uninstalling, the package list and their configuration files from /etc are saved in {dir} — "
              "together with a restore.sh script that installs them back.",
}


def backup_text(method):
    return tr(BACKUP_TEXT.get(method, BACKUP_TEXT["config"]), dir=str(BACKUP_DIR))


def helper_argv(*args):
    """Command that runs the root helper (through pkexec / polkit)."""
    here = Path(__file__).resolve().parent
    args = ("--lang", i18n.LANG, *args)
    if INSTALLED_HELPER.exists() and str(here).startswith(str(INSTALLED_PKG_DIR)):
        return ["pkexec", str(INSTALLED_HELPER), *args]
    return ["pkexec", sys.executable, "-I", str(here / "helper.py"), *args]


# ───────────────────────────── program model ─────────────────────────────

@dataclass
class App:
    kind: str
    ident: str
    name: str
    version: str = ""
    size: int = 0
    summary: str = ""
    icon: str = ""
    manual: bool = True
    is_app: bool = True
    essential: bool = False
    priority: str = ""
    section: str = ""
    extra: str = ""
    installed: float = 0
    desktops: list = field(default_factory=list)

    @property
    def key(self):
        return (self.kind, self.ident, self.extra)

    @property
    def is_program(self):
        """Whether to show it in the default view (applications and tools, no libraries)."""
        if self.kind != "apt":
            return True
        if self.is_app:
            return True
        return (self.manual and self.priority not in ("required", "important", "standard")
                and self.section not in HIDDEN_SECTIONS and not self.ident.startswith("lib"))


def dpkg_install_dates():
    dates = {}
    for f in sorted(glob.glob("/var/log/dpkg.log*"), key=mtime):
        try:
            opener = gzip.open if f.endswith(".gz") else open
            with opener(f, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    p = line.split()
                    if len(p) >= 4 and p[2] == "install":
                        try:
                            dates[p[3].split(":")[0]] = datetime.strptime(
                                p[0] + " " + p[1], "%Y-%m-%d %H:%M:%S").timestamp()
                        except ValueError:
                            pass
        except OSError:
            pass
    return dates


def collect_apt():
    if not have("dpkg-query"):
        return []
    fmt = ("${db:Status-Abbrev}\t${binary:Package}\t${Version}\t${Installed-Size}\t"
           "${Essential}\t${Priority}\t${Section}\t${binary:Summary}\n")
    text = out(["dpkg-query", "-W", "-f", fmt])
    manual = set(out(["apt-mark", "showmanual"]).split())
    dates = dpkg_install_dates()
    dmap = {}
    for lf in glob.glob("/var/lib/dpkg/info/*.list"):
        pkg = os.path.basename(lf)[:-5]
        try:
            with open(lf, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.startswith("/usr/share/applications/") and line.rstrip().endswith(".desktop"):
                        dmap.setdefault(pkg, []).append(line.rstrip())
        except OSError:
            pass
    apps = []
    for line in text.splitlines():
        p = line.split("\t")
        if len(p) < 8 or not p[0].startswith("ii"):
            continue
        _st, pkg, ver, isize, ess, prio, sect, summ = p[:8]
        bare = pkg.split(":")[0]
        a = App("apt", pkg, bare, ver, int(isize) * 1024 if isize.isdigit() else 0, summ)
        a.manual = bare in manual
        a.essential = ess.strip().lower() == "yes"
        a.priority = prio.strip()
        a.section = sect.strip().split("/")[-1]
        a.installed = dates.get(bare, 0)
        best = None
        for d in dmap.get(pkg) or dmap.get(bare) or []:
            a.desktops.append(d)
            info = parse_desktop(d)
            if info and not info["hidden"] and best is None:
                best = info
        a.is_app = best is not None
        if best:
            a.name, a.icon = best["name"], best["icon"]
            if best["comment"]:
                a.summary = best["comment"]
        apps.append(a)
    return apps


def collect_flatpak():
    if not have("flatpak"):
        return []
    text = out(["flatpak", "list", "--app", "--columns=application,name,version,size,installation"])
    apps = []
    for line in text.splitlines():
        p = line.split("\t")
        if len(p) < 5 or "." not in p[0]:
            continue
        a = App("flatpak", p[0].strip(), p[1].strip() or p[0], p[2].strip(), parse_hsize(p[3]), p[0])
        a.extra = p[4].strip() or "system"
        a.icon = a.ident
        base = HOME / ".local/share/flatpak" if a.extra == "user" else Path("/var/lib/flatpak")
        a.installed = mtime(base / "app" / a.ident)
        info = parse_desktop(base / "exports/share/applications" / f"{a.ident}.desktop")
        if info:
            a.desktops.append(info["path"])
            a.summary = info["comment"] or a.summary
        apps.append(a)
    return apps


def collect_snap():
    if not have("snap"):
        return []
    text = out(["snap", "list"], timeout=60)
    apps = []
    for line in text.splitlines()[1:]:
        p = line.split()
        if len(p) < 4:
            continue
        name, ver = p[0], p[1]
        notes = p[-1] if len(p) >= 6 else ""
        if (name in ("snapd", "bare") or name.startswith("core") or "base" in notes
                or "snapd" in notes or re.match(r"^(gnome-\d|kde-frameworks|gtk-common-themes|mesa-)", name)):
            continue
        files = glob.glob(f"/var/lib/snapd/snaps/{name}_*.snap")
        a = App("snap", name, name, ver, sum(os.path.getsize(f) for f in files), "Snap")
        a.installed = min((mtime(f) for f in files), default=0)
        for d in glob.glob(f"/var/lib/snapd/desktop/applications/{name}_*.desktop"):
            info = parse_desktop(d)
            if info:
                a.desktops.append(d)
                a.name, a.icon = info["name"], info["icon"]
                a.summary = info["comment"] or a.summary
                break
        apps.append(a)
    return apps


def collect_appimage(desks):
    apps, seen = [], set()
    for d in APPIMAGE_DIRS:
        if not d.is_dir():
            continue
        cands = list(d.glob("*")) + (list(d.glob("*/*")) if d == Path("/opt") else [])
        for f in cands:
            try:
                if not f.is_file() or not f.name.lower().endswith(".appimage"):
                    continue
                rp = str(f.resolve())
                st = f.stat()
            except OSError:
                continue
            if rp in seen:
                continue
            seen.add(rp)
            stem = f.name[:-9]
            clean = re.split(r"[-_ .]v?\d", stem)[0] or stem
            m = re.search(r"(\d+(?:\.\d+)+)", stem)
            a = App("appimage", str(f), clean, m.group(1) if m else "", st.st_size, tr("AppImage program"))
            a.installed = st.st_mtime
            for info in desks:
                if str(f) in info["exec"] or rp in info["exec"]:
                    a.desktops.append(info["path"])
                    a.name, a.icon = info["name"], info["icon"]
                    a.summary = info["comment"] or a.summary
            apps.append(a)
    return apps


def collect_opt(desks):
    try:
        entries = [p for p in Path("/opt").iterdir() if p.is_dir() and not p.is_symlink()]
    except OSError:
        return []
    if not entries:
        return []
    owned = dpkg_owned(str(p) for p in entries)
    apps = []
    for p in entries:
        if str(p) in owned:
            continue
        try:
            if all(x.name.lower().endswith(".appimage") for x in p.iterdir()):
                continue
        except OSError:
            continue
        a = App("opt", str(p), p.name, "", 0, tr("Program installed manually in /opt"))
        a.installed = mtime(p)
        _rc, o, _e = run(["du", "-sb", str(p)], timeout=60)
        if o.split() and o.split()[0].isdigit():
            a.size = int(o.split()[0])
        for info in desks:
            if str(p) + "/" in info["exec"]:
                a.desktops.append(info["path"])
                a.name, a.icon = info["name"], info["icon"]
                a.summary = info["comment"] or a.summary
        apps.append(a)
    return apps


def collect_all():
    desks = all_desktops()
    apps = []
    for fn in (collect_apt, collect_flatpak, collect_snap):
        try:
            apps += fn()
        except Exception as e:  # noqa: BLE001
            print(f"{fn.__name__}: {e}", file=sys.stderr)
    for fn in (collect_appimage, collect_opt):
        try:
            apps += fn(desks)
        except Exception as e:  # noqa: BLE001
            print(f"{fn.__name__}: {e}", file=sys.stderr)
    return apps


# ───────────────────────────── leftovers ─────────────────────────────

@dataclass
class Cand:
    path: str
    where: str
    sure: bool
    root: bool
    size: int = 0


def norm_tokens(words):
    res = set()
    for w in words:
        w = (w or "").strip().lower()
        if not w:
            continue
        for v in {w, w.replace(" ", ""), w.replace(" ", "-"), w.replace(" ", "_")}:
            if len(v) >= 3 and v not in GENERIC and "/" not in v:
                res.add(v)
    return res


def tokens_for_app(a):
    words = []
    if a.kind == "apt":
        base = a.ident.split(":")[0]
        words.append(base)
        for suf in APT_SUFFIXES:
            if base.endswith(suf):
                words.append(base[:-len(suf)])
    elif a.kind == "flatpak":
        words += [a.ident, a.ident.split(".")[-1]]
    elif a.kind == "snap":
        words.append(a.ident)
    elif a.kind == "appimage":
        words.append(re.split(r"[-_ .]v?\d", Path(a.ident).name[:-9])[0])
    elif a.kind == "opt":
        words.append(Path(a.ident).name)
    for d in a.desktops:
        stem = Path(d).stem
        words.append(stem)
        if stem.count(".") >= 2:
            words.append(stem.split(".")[-1])
        info = parse_desktop(d)
        if info:
            exe = exec_basename(info["exec"])
            if exe and not exe.lower().endswith(".appimage") and exe not in ("flatpak", "snap", "env"):
                words.append(re.split(r"[-_]\d", exe)[0])
    if a.name and len(a.name) <= 25 and len(a.name.split()) <= 2:
        words.append(a.name)
    return norm_tokens(words)


EXACT_SUFFIXES = ("", "rc", ".conf", ".desktop", ".service", ".timer", ".list", ".sources",
                  ".gpg", ".asc", ".json", ".ini", ".log", ".cfg", ".appimage", ".sh")


def match_name(name, tokens):
    n = name.lower()
    nd = n[1:] if n.startswith(".") else n
    for t in tokens:
        for suf in EXACT_SUFFIXES:
            if nd == t + suf:
                return "exact"
        parts = nd.split(".")
        if len(parts) >= 3 and parts[-1] == t:
            return "exact"
    for t in tokens:
        for sep in "-_.":
            if nd.startswith(t + sep):
                return "prefix"
        if "." in nd and ("." + t + ".") in ("." + nd + "."):
            return "prefix"
    return None


USER_SCAN = [
    (HOME, "Hidden file in home folder", {"dot_only": True}),
    (HOME / ".config", "Configuration", {}),
    (HOME / ".local/share", "Application data", {}),
    (HOME / ".local/state", "Application state", {}),
    (HOME / ".cache", "Cache", {}),
    (HOME / ".var/app", "Flatpak data", {}),
    (HOME / ".config/autostart", "Autostart", {"desktop_exec": True}),
    (HOME / ".local/share/applications", "Menu entry", {"desktop_exec": True}),
    (HOME / ".config/systemd/user", "User systemd service", {}),
    (HOME / ".local/bin", "Executable", {}),
]
SYS_SCAN = [
    (Path("/etc"), "System configuration", {}),
    (Path("/var/lib"), "System data", {}),
    (Path("/var/cache"), "System cache", {}),
    (Path("/var/log"), "Logs", {}),
    (Path("/opt"), "Program in /opt", {}),
    (Path("/usr/local/share"), "Data in /usr/local", {}),
    (Path("/usr/local/lib"), "Libraries in /usr/local", {}),
    (Path("/usr/local/bin"), "Executable (/usr/local)", {}),
    (Path("/etc/apt/sources.list.d"), "APT repository", {}),
    (Path("/etc/apt/keyrings"), "Repository key", {}),
    (Path("/usr/share/keyrings"), "Repository key", {}),
    (Path("/etc/apt/trusted.gpg.d"), "Repository key", {}),
    (Path("/etc/systemd/system"), "systemd service", {}),
    (Path("/etc/xdg/autostart"), "System autostart", {"desktop_exec": True}),
    (Path("/usr/share/applications"), "Menu entry (system)", {"desktop_exec": True}),
    (Path("/usr/local/share/applications"), "Menu entry (/usr/local)", {"desktop_exec": True}),
]
SYS_PARENTS = {str(d) for d, _w, _o in SYS_SCAN}
ALLOWED_PARENTS = {str(d) for d, _w, _o in USER_SCAN} | SYS_PARENTS


def names_in_use():
    names = set()
    for line in out(["dpkg-query", "-W", "-f", "${db:Status-Abbrev} ${Package}\n"]).splitlines():
        if line.startswith("ii"):
            names.add(line.split()[-1].lower())
    if have("flatpak"):
        names |= {x.strip().lower() for x in out(["flatpak", "list", "--app", "--columns=application"]).split()}
    return names


def scan_leftovers(tokens):
    tokens = {t for t in tokens if t}
    if not tokens:
        return []
    in_use = names_in_use()
    cands = {}

    def add(path, where, level, root):
        name = os.path.basename(path)
        if path in PROTECTED_PATHS or (root and name in PROTECTED_SYS_NAMES):
            return
        bare = name.lower().lstrip(".")
        if bare in in_use or Path(bare).stem in in_use:
            return
        if path in cands:
            cands[path].sure = cands[path].sure or level == "exact"
            return
        cands[path] = Cand(path, where, level == "exact", root)

    for group, root in ((USER_SCAN, False), (SYS_SCAN, True)):
        for d, where, opts in group:
            try:
                entries = list(os.scandir(d))
            except OSError:
                continue
            for e in entries:
                if opts.get("dot_only") and not e.name.startswith("."):
                    continue
                lvl = match_name(e.name, tokens)
                if not lvl and opts.get("desktop_exec") and e.name.endswith(".desktop"):
                    info = parse_desktop(e.path)
                    if info:
                        exe = exec_basename(info["exec"]).lower()
                        if exe and (exe in tokens or re.split(r"[-_]\d", exe)[0] in tokens):
                            lvl = "exact"
                if lvl:
                    add(e.path, where, lvl, root)

    for p in dpkg_owned([p for p, c in cands.items() if c.root]):
        cands.pop(p, None)
    res = list(cands.values())
    for c in res:
        c.size = path_size(c.path)
    res.sort(key=lambda c: (c.root, not c.sure, c.where, c.path))
    return res


def is_safe(p, system_only=False):
    p = os.path.normpath(p)
    if not os.path.isabs(p) or ".." in Path(p).parts or len(Path(p).parts) < 3:
        return False
    if p in PROTECTED_PATHS:
        return False
    if system_only:
        if p.startswith(("/home/", "/root/")):
            return False
        return str(Path(p).parent) in SYS_PARENTS and os.path.basename(p) not in PROTECTED_SYS_NAMES
    if not p.startswith(str(HOME) + "/") and os.path.basename(p) in PROTECTED_SYS_NAMES:
        return False
    return str(Path(p).parent) in ALLOWED_PARENTS


def move_to_trash(p):
    trash = Path(os.environ.get("XDG_DATA_HOME", str(HOME / ".local/share"))) / "Trash"
    files, info = trash / "files", trash / "info"
    files.mkdir(parents=True, exist_ok=True)
    info.mkdir(parents=True, exist_ok=True)
    name = os.path.basename(p)
    dest, i = files / name, 1
    while os.path.lexists(dest) or (info / (dest.name + ".trashinfo")).exists():
        dest = files / f"{name}.{i}"
        i += 1
    (info / (dest.name + ".trashinfo")).write_text(
        f"[Trash Info]\nPath={urllib.parse.quote(str(p))}\n"
        f"DeletionDate={datetime.now():%Y-%m-%dT%H:%M:%S}\n", encoding="utf-8")
    shutil.move(str(p), str(dest))


def delete_candidates(cands, to_trash=True):
    ok, msgs = 0, []
    for c in [c for c in cands if not c.root]:
        if not is_safe(c.path):
            msgs.append(tr("Skipped (unsafe path): {p}", p=c.path))
            continue
        try:
            if to_trash:
                move_to_trash(c.path)
            elif os.path.isdir(c.path) and not os.path.islink(c.path):
                shutil.rmtree(c.path)
            else:
                os.unlink(c.path)
            ok += 1
            log(tr("LEFTOVER → Trash: {p}", p=c.path) if to_trash else tr("LEFTOVER deleted: {p}", p=c.path))
        except Exception as e:  # noqa: BLE001
            msgs.append(tr("Error: {p}: {e}", p=c.path, e=e))
    roots = [c.path for c in cands if c.root and is_safe(c.path, system_only=True)]
    if roots:
        rc, _o, e = run(helper_argv("remove-paths", *roots), timeout=900)
        if rc == 0:
            ok += len(roots)
            for p in roots:
                log(tr("LEFTOVER deleted (system): {p}", p=p))
        elif rc in (126, 127):
            msgs.append(tr("System files were not deleted: password entry was cancelled."))
        else:
            msgs.append(tr("System files were not deleted: {e}", e=(e or _o).strip()[-300:] or rc))
    return ok, msgs


def check_cleanup():
    _rc, o, _e = run(["apt-get", "-s", "autoremove", "--purge"])
    orphans = [m.group(2) for m in re.finditer(r"^(Remv|Purg) (\S+)", o, re.M)]
    rc_pkgs = [ln.split()[1] for ln in out(["dpkg-query", "-W", "-f",
               "${db:Status-Abbrev} ${binary:Package}\n"]).splitlines() if ln.startswith("rc")]
    debs = glob.glob("/var/cache/apt/archives/*.deb")
    cache = sum(os.path.getsize(f) for f in debs)
    orphan_size = 0
    if orphans:
        fmt = "${Installed-Size}\n"
        for s in out(["dpkg-query", "-W", "-f", fmt, *orphans]).split():
            if s.isdigit():
                orphan_size += int(s) * 1024
    return {"orphans": orphans, "orphan_size": orphan_size, "rc": rc_pkgs,
            "cache": cache, "cache_files": len(debs)}


def simulate_purge(pkgs):
    rc, o, e = run(["apt-get", "-s", "purge", *pkgs])
    removed = [m.group(2) for m in re.finditer(r"^(Remv|Purg) (\S+)", o, re.M)]
    return rc, removed, e
