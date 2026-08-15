#!/usr/bin/env bash
# 打 amd64 deb 包(自带 Electron 运行时,自包含)
# 用法: ./packaging/build-deb.sh   (ELECTRON_DIST / VERSION 可用环境变量覆盖)
set -e
cd "$(dirname "$(readlink -f "$0")")/.."

VER="${VERSION:-1.0.0}"
DIST="${ELECTRON_DIST:-./node_modules/electron/dist}"
[ -x "$DIST/electron" ] || { echo "未找到 Electron 运行时: $DIST(先 npm install)"; exit 1; }
command -v convert >/dev/null || { echo "需要 imagemagick(convert)"; exit 1; }

PKG=netease-cloud-music-linux
WORK=$(mktemp -d)
ROOT="$WORK/$PKG"
mkdir -p "$ROOT/DEBIAN" "$ROOT/opt/netease-cloud-music" "$ROOT/usr/share/applications"

# 程序文件
cp main.js run.sh netease-tray-helper.py icon.png package.json "$ROOT/opt/netease-cloud-music/"
chmod 755 "$ROOT/opt/netease-cloud-music/run.sh" "$ROOT/opt/netease-cloud-music/netease-tray-helper.py"

# Electron 运行时
mkdir -p "$ROOT/opt/netease-cloud-music/electron"
cp -a "$DIST"/. "$ROOT/opt/netease-cloud-music/electron/"
rm -f "$ROOT/opt/netease-cloud-music/electron/netease-music" # 打包内不保留硬链接副本

# 图标
for s in 16 24 32 48 64 96 128 256; do
  d="$ROOT/usr/share/icons/hicolor/${s}x${s}/apps"
  mkdir -p "$d"
  convert icon.png -resize "${s}x${s}" "$d/netease-cloud-music.png"
done

# 桌面入口
cp netease-cloud-music.desktop "$ROOT/usr/share/applications/"

# 控制信息
INSTALLED_SIZE=$(du -ks "$ROOT" | awk '{print $1}')
cat > "$ROOT/DEBIAN/control" <<EOF
Package: $PKG
Version: $VER
Architecture: amd64
Maintainer: lujinda <lujinda@users.noreply.github.com>
Depends: python3, python3-gi, gir1.2-gtk-3.0, gir1.2-gdkpixbuf-2.0
Installed-Size: $INSTALLED_SIZE
Section: sound
Priority: optional
Description: NetEase Cloud Music web player desktop wrapper (Electron)
 Wraps music.163.com/st/webplayer as a Linux desktop app:
 tray-resident playback, tray icon menu, single instance, persistent login.
EOF

cat > "$ROOT/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
# 硬链接改名:让 WM_CLASS 与 .desktop 的 StartupWMClass 对应
ln -f /opt/netease-cloud-music/electron/electron \
      /opt/netease-cloud-music/electron/netease-music 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
EOF
cat > "$ROOT/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
EOF
chmod 755 "$ROOT/DEBIAN/postinst" "$ROOT/DEBIAN/postrm"

OUT="${PKG}_${VER}_amd64.deb"
dpkg-deb --build --root-owner-group -Zxz "$ROOT" "$OUT"
rm -rf "$WORK"
echo "OK: $(du -h "$OUT" | awk '{print $1}') -> $OUT"
