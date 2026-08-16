#!/usr/bin/env python3
"""网易云音乐托盘辅助进程(自实现 StatusNotifierItem 协议)。

Electron 自带托盘与 libappindicator/ayatana 在部分桌面下注册或菜单异常,
因此直接用 Gio 实现 StatusNotifierItem + dbusmenu 协议(与 fcitx、copyq
同款通道),在右上角系统托盘提供图标:
  - 显示 / 隐藏主窗口
  - 退出网易云音乐
通过 127.0.0.1 本地接口指挥 Electron 主进程;主进程退出后本进程自动退出。
"""
import os
import urllib.request

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf, GLib, Gio, Gtk

PORT = 46321
BASE = 'http://127.0.0.1:%d' % PORT
BUS_NAME = 'org.kde.StatusNotifierItem-%d-1' % os.getpid()
ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.png')

SNI_XML = '''
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="Activate">
      <arg type="i" direction="in"/><arg type="i" direction="in"/>
    </method>
    <method name="ContextMenu">
      <arg type="i" direction="in"/><arg type="i" direction="in"/>
    </method>
    <method name="Scroll">
      <arg type="i" direction="in"/><arg type="s" direction="in"/>
    </method>
  </interface>
</node>
'''

MENU_XML = '''
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <method name="GetLayout">
      <arg type="i" direction="in"/>
      <arg type="i" direction="in"/>
      <arg type="as" direction="in"/>
      <arg type="u" direction="out"/>
      <arg type="(ia{sv}av)" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" direction="in"/>
      <arg type="as" direction="in"/>
      <arg type="a(ia{sv})" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg type="i" direction="in"/>
      <arg type="s" direction="in"/>
      <arg type="v" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" direction="in"/>
      <arg type="s" direction="in"/>
      <arg type="v" direction="in"/>
      <arg type="u" direction="in"/>
    </method>
    <method name="AboutToShow">
      <arg type="i" direction="in"/>
      <arg type="b" direction="out"/>
    </method>
  </interface>
</node>
'''

# 菜单项 id:1=切换窗口 2=分隔符 3=退出
MENU_TOGGLE, MENU_SEP, MENU_QUIT = 1, 2, 3


def cmd(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=2) as resp:
            return resp.read()
    except Exception:
        return None


def load_icon_pixmap():
    """把 PNG 转成 StatusNotifier 的 IconPixmap(ARGB32 字节序)。"""
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(ICON_PATH, 48, 48)
    if not pixbuf.get_has_alpha():
        pixbuf = pixbuf.add_alpha(True, 0, 0, 0)
    w, h = pixbuf.get_width(), pixbuf.get_height()
    rowstride = pixbuf.get_rowstride()
    pixels = pixbuf.get_pixels()
    if not pixels:
        return (w, h, b'')
    out = bytearray()
    for y in range(h):
        row = y * rowstride
        for x in range(w):
            i = row + x * 4
            r, g, b, a = pixels[i], pixels[i + 1], pixels[i + 2], pixels[i + 3]
            out += bytes((a, r, g, b))  # ARGB
    return (w, h, bytes(out))


ICON_PIXMAP = None


class TrayService:
    def __init__(self, connection):
        self.conn = connection
        sni = Gio.DBusNodeInfo.new_for_xml(SNI_XML)
        menu = Gio.DBusNodeInfo.new_for_xml(MENU_XML)
        connection.register_object(
            '/StatusNotifierItem', sni.interfaces[0],
            self.on_method, self.on_get_prop, None)
        connection.register_object(
            '/MenuBar', menu.interfaces[0],
            self.on_menu_method, self.on_menu_get_prop, None)

    # ---------- StatusNotifierItem ----------
    def on_method(self, conn, sender, path, iface, method, params, invocation):
        if method == 'Activate':  # 左键单击:切换窗口
            cmd('/toggle')
        invocation.return_value(None)

    def on_get_prop(self, conn, sender, path, iface, prop):
        global ICON_PIXMAP
        if prop == 'Category':
            return GLib.Variant('s', 'ApplicationStatus')
        if prop == 'Id':
            return GLib.Variant('s', 'netease-cloud-music')
        if prop == 'Title':
            return GLib.Variant('s', '网易云音乐(非官方封装)')
        if prop == 'Status':
            return GLib.Variant('s', 'Active')
        if prop == 'WindowId':
            return GLib.Variant('i', 0)
        if prop == 'IconName':
            return GLib.Variant('s', 'netease-cloud-music')
        if prop == 'IconPixmap':
            if ICON_PIXMAP is None:
                try:
                    ICON_PIXMAP = load_icon_pixmap()
                except Exception as e:
                    print('icon load failed:', e)
                    ICON_PIXMAP = (0, 0, b'')
            w, h, data = ICON_PIXMAP
            return GLib.Variant('a(iiay)', [(w, h, data)])
        if prop == 'ToolTip':
            return GLib.Variant('(sa(iiay)ss)', ('', [], '网易云音乐(非官方封装)', ''))
        if prop == 'Menu':
            return GLib.Variant('o', '/MenuBar')
        return None

    # ---------- dbusmenu ----------
    # gi 的 Variant 文本构造器:av 的元素须为已构造 Variant,
    # 其余层级传纯 Python 嵌套数据,叶子值包成 Variant('s', ...)
    @staticmethod
    def _item(i, props):
        return GLib.Variant(
            '(ia{sv}av)', (i, {k: GLib.Variant('s', v) for k, v in props.items()}, []))

    def layout(self):
        children = [
            self._item(MENU_TOGGLE, {'label': '显示 / 隐藏主窗口'}),
            self._item(MENU_SEP, {'type': 'separator'}),
            self._item(MENU_QUIT, {'label': '退出'}),
        ]
        return (0, {'children-display': GLib.Variant('s', 'submenu')}, children)

    def on_menu_method(self, conn, sender, path, iface, method, params, invocation):
        if method == 'GetLayout':
            invocation.return_value(
                GLib.Variant('(u(ia{sv}av))', (1, self.layout())))
        elif method == 'GetGroupProperties':
            # dbusmenu 方法返回值必须包成元组 variant
            invocation.return_value(GLib.Variant('(a(ia{sv}))', ([],)))
        elif method == 'GetProperty':
            invocation.return_value(
                GLib.Variant('(v)', (GLib.Variant('s', ''),)))
        elif method == 'Event':
            item_id, event = params.unpack()[0:2]
            if event == 'clicked':
                if item_id == MENU_TOGGLE:
                    cmd('/toggle')
                elif item_id == MENU_QUIT:
                    cmd('/quit')
                    GLib.idle_add(Gtk.main_quit)
            invocation.return_value(None)
        elif method == 'AboutToShow':
            invocation.return_value(GLib.Variant('(b)', (False,)))
        else:
            invocation.return_value(None)

    def on_menu_get_prop(self, conn, sender, path, iface, prop):
        if prop == 'Version':
            return GLib.Variant('u', 3)
        return None


_seen_alive = False
_fail_streak = 0


def watch_app():
    """轮询主进程:启动期容忍短暂失败;运行期主进程消失则随之退出。"""
    global _seen_alive, _fail_streak
    if cmd('/ping') is not None:
        _seen_alive = True
        _fail_streak = 0
        return True
    _fail_streak += 1
    if _seen_alive or _fail_streak >= 20:  # 启动宽限 ~30s
        Gtk.main_quit()
        return False
    return True


def on_bus_acquired(conn, result):
    TrayService(conn)
    # 向 watcher 显式注册(传自己的总线名)
    try:
        conn.call(
            'org.kde.StatusNotifierWatcher', '/StatusNotifierWatcher',
            'org.kde.StatusNotifierWatcher', 'RegisterStatusNotifierItem',
            GLib.Variant('(s)', (BUS_NAME,)), None,
            Gio.DBusCallFlags.NONE, 2000, None, None)
    except Exception as e:
        print('watcher register:', e)


def main():
    Gio.bus_own_name(
        Gio.BusType.SESSION, BUS_NAME,
        Gio.BusNameOwnerFlags.NONE,
        on_bus_acquired, None, None)
    GLib.timeout_add(1500, watch_app)
    Gtk.main()


if __name__ == '__main__':
    main()
