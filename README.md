# netease-cloud-music-linux

网易云音乐网页播放器 ([music.163.com/st/webplayer](https://music.163.com/st/webplayer)) 的 Linux 桌面封装。Electron 壳 + 自实现 StatusNotifier 托盘。

- 点 ✕ 不退出,最小化驻留后台继续播放;托盘菜单可显示/退出
- 托盘图标与输入法同列(自实现 StatusNotifierItem 协议,兼容 GNOME/KDE 等)
- 单实例、登录态持久化、`Ctrl+Q` 退出

## 安装(Releases 的 deb 包)

```bash
sudo apt install ./netease-cloud-music-linux_*_amd64.deb
```

## 源码运行

依赖:Node.js、python3-gi、gir1.2-gtk-3.0、gir1.2-gdkpixbuf-2.4

```bash
npm install
./run.sh
```

## 打包 deb

```bash
npm install                 # 下载 Electron 运行时
./packaging/build-deb.sh    # 产出 netease-cloud-music-linux_<ver>_amd64.deb
```

## 卸载

```bash
sudo apt remove netease-cloud-music-linux
```

---

## 声明

本项目为**非官方**开源封装,与网易、网易云音乐无任何关联,仅供个人学习使用。
「网易云音乐」名称与标识的知识产权归网易公司所有;本项目不用于任何商业目的。
如认为本项目侵犯您的合法权益,请提交 Issue,将立即删除相关内容。

本项目的代码由 Qwen3.8 Max 生成。
