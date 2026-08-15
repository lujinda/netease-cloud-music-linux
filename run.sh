#!/usr/bin/env bash
# 网易云音乐(Web 封装版)启动器
set -e
cd "$(dirname "$(readlink -f "$0")")"

# Electron 运行时:安装后在 ./electron(deb 包内),源码运行在 node_modules
if [ -d ./electron ]; then DIST=./electron; else DIST=./node_modules/electron/dist; fi

# 用硬链接改名启动:Chromium 以可执行文件名作为 WM_CLASS,
# 让 GNOME 把窗口与 .desktop 的 StartupWMClass/图标关联起来
# (软链接会被 /proc/self/exe 解析回 electron,故必须用硬链接)
# 安装版(deb)的硬链接由 postinst 以 root 建好;源码目录才在这里建
BIN="$DIST/netease-music"
if [ -L "$BIN" ]; then rm -f "$BIN"; fi
if [ ! -e "$BIN" ] && [ -w "$DIST" ]; then ln "$DIST/electron" "$BIN"; fi
[ -e "$BIN" ] || BIN="$DIST/electron" # 兜底:WM_CLASS 不对但能用

# 托盘辅助进程:右上角图标 + 菜单(与输入法同款的 StatusNotifier 通道)
if ! pgrep -f netease-tray-helper.py >/dev/null; then
  mkdir -p "$HOME/.cache/netease-cloud-music"
  nohup python3 ./netease-tray-helper.py \
    >>"$HOME/.cache/netease-cloud-music/tray-helper.log" 2>&1 &
fi

exec "$BIN" . "$@"
