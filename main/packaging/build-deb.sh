#!/bin/bash
# Builds linux-software-uninstaller_<version>_all.deb — run from the project folder: ./packaging/build-deb.sh
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(python3 -c 'import re;print(re.search(r"VERSION = \"(.+?)\"", open("linux_software_uninstaller/__init__.py").read()).group(1))')
PKG=linux-software-uninstaller
OUT="${PKG}_${VERSION}_all.deb"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

install -d "$STAGE/DEBIAN" \
           "$STAGE/usr/bin" \
           "$STAGE/usr/libexec/linux-software-uninstaller" \
           "$STAGE/usr/share/linux-software-uninstaller/linux_software_uninstaller" \
           "$STAGE/usr/share/applications" \
           "$STAGE/usr/share/metainfo" \
           "$STAGE/usr/share/polkit-1/actions" \
           "$STAGE/usr/share/icons/hicolor/scalable/apps" \
           "$STAGE/usr/share/doc/$PKG"

install -m 644 linux_software_uninstaller/*.py "$STAGE/usr/share/linux-software-uninstaller/linux_software_uninstaller/"
install -m 755 linux_software_uninstaller/helper.py "$STAGE/usr/libexec/linux-software-uninstaller/lsu-helper"
install -m 644 data/linux-software-uninstaller.desktop "$STAGE/usr/share/applications/"
install -m 644 data/linux-software-uninstaller.metainfo.xml "$STAGE/usr/share/metainfo/"
install -m 644 data/linux-software-uninstaller.policy "$STAGE/usr/share/polkit-1/actions/"
install -m 644 data/linux-software-uninstaller.svg "$STAGE/usr/share/icons/hicolor/scalable/apps/"
install -m 644 README.md "$STAGE/usr/share/doc/$PKG/"
install -m 644 debian/README.Debian debian/copyright "$STAGE/usr/share/doc/$PKG/"
gzip -9n -c debian/changelog > "$STAGE/usr/share/doc/$PKG/changelog.Debian.gz"
chmod 644 "$STAGE/usr/share/doc/$PKG/changelog.Debian.gz"

cat > "$STAGE/usr/bin/linux-software-uninstaller" <<'EOF'
#!/usr/bin/python3 -I
import sys
sys.path.insert(0, "/usr/share/linux-software-uninstaller")
from linux_software_uninstaller.app import main
main()
EOF
chmod 755 "$STAGE/usr/bin/linux-software-uninstaller"

SIZE=$(du -sk --exclude=DEBIAN "$STAGE" | cut -f1)
cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Architecture: all
Section: admin
Priority: optional
Installed-Size: $SIZE
Maintainer: Linux Software Uninstaller <linux-software-uninstaller@localhost>
Depends: python3 (>= 3.11), python3-pyqt6, pkexec | policykit-1, apt, dpkg, util-linux
Recommends: qt6-svg-plugins, btrfs-progs
Conflicts: deinstalator
Replaces: deinstalator
Suggests: flatpak, snapper
Homepage: https://github.com/USERNAME/linux-software-uninstaller
Description: remove programs together with their leftovers
 Linux Software Uninstaller is a graphical IObit Uninstaller-style tool for
 Debian and KDE Plasma. It lists programs from APT, Flatpak, Snap, AppImage
 and /opt in one window, uninstalls them together with their configuration,
 finds leftover files, cleans up orphaned dependencies and can back up the
 system (btrfs/snapper, Timeshift or package configuration) before removal.
 .
 The interface is available in English and Polish.
EOF

cat > "$STAGE/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
# User settings (~/.config/linux-software-uninstaller, ~/.local/state/linux-software-uninstaller) are left untouched.
exit 0
EOF
chmod 755 "$STAGE/DEBIAN/postrm"

find "$STAGE" -name '__pycache__' -prune -exec rm -rf {} +
(cd "$STAGE" && find usr -type f -exec md5sum {} + > DEBIAN/md5sums)
dpkg-deb --root-owner-group -Zxz --build "$STAGE" "$OUT" >/dev/null
echo "Built: $OUT"
