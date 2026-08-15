'use strict';

const { app, BrowserWindow, Menu, shell, session } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');

const TARGET_URL = 'https://music.163.com/st/webplayer';
const APP_NAME = '网易云音乐';
const PARTITION = 'persist:netease'; // 持久化会话,保存登录状态/Cookie
// 托盘辅助进程(netease-tray-helper.py)通过该本地接口控制应用
const CONTROL_PORT = 46321;

let mainWindow = null;
let isQuitting = false; // true 时才是真正退出;否则点关闭按钮只最小化驻留

// 固定应用名,userData 目录与菜单标题以此为准
app.setName('netease-cloud-music');

// 关键事件落盘,便于排查(~/.config/netease-cloud-music/main.log)
function log(...args) {
  const line = `[${new Date().toISOString()}] ${args.join(' ')}\n`;
  try {
    fs.appendFileSync(path.join(app.getPath('userData'), 'main.log'), line);
  } catch {}
  process.stdout.write(line);
}

// 退出:先走正常 quit;若 2 秒内没退成(关闭事件被卡住等),强制退出兜底
function quitApp() {
  log('quit requested');
  isQuitting = true;
  app.quit();
  setTimeout(() => {
    log('quit did not finish in 2s, force exit');
    app.exit(0);
  }, 2000);
}

// ---------- 单实例:再次启动时恢复并聚焦已有窗口 ----------
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => showWindow());

  function showWindow() {
    if (!mainWindow) {
      createWindow();
      return;
    }
    if (!mainWindow.isVisible()) mainWindow.show();
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.moveTop();
    mainWindow.focus();
  }

  function toggleWindow() {
    if (!mainWindow || mainWindow.isMinimized() || !mainWindow.isVisible()) {
      showWindow();
    } else {
      log('control: toggle -> minimize');
      mainWindow.minimize();
    }
  }

  // ---------- 本地控制接口:供托盘辅助进程调用 ----------
  function startControlServer() {
    const server = http.createServer((req, res) => {
      res.setHeader('Content-Type', 'text/plain');
      if (req.url === '/ping') {
        res.end('pong');
      } else if (req.url === '/toggle') {
        toggleWindow();
        res.end('ok');
      } else if (req.url === '/quit') {
        res.end('bye');
        setTimeout(quitApp, 50); // 先回包再退出
      } else {
        res.statusCode = 404;
        res.end();
      }
    });
    server.on('error', (e) => log('control server error:', e.message));
    server.listen(CONTROL_PORT, '127.0.0.1', () =>
      log('control server listening on', CONTROL_PORT)
    );
  }

  // ---------- 菜单(含复制/粘贴、缩放、媒体键) ----------
  function buildMenu() {
    const template = [
      {
        label: '文件',
        submenu: [{ label: '退出', accelerator: 'CmdOrCtrl+Q', click: quitApp }]
      },
      { role: 'editMenu', label: '编辑' },
      {
        label: '视图',
        submenu: [
          { role: 'reload', label: '刷新' },
          { role: 'forceReload', label: '强制刷新' },
          { type: 'separator' },
          { role: 'zoomIn', label: '放大' },
          { role: 'zoomOut', label: '缩小' },
          { role: 'resetZoom', label: '重置缩放' },
          { type: 'separator' },
          { role: 'togglefullscreen', label: '全屏' }
        ]
      },
      {
        label: '播放',
        submenu: [
          { role: 'mediaPlayPause', label: '播放 / 暂停' },
          { role: 'mediaNextTrack', label: '下一首' },
          { role: 'mediaPreviousTrack', label: '上一首' },
          { role: 'mediaStop', label: '停止' }
        ]
      },
      {
        role: 'help',
        label: '帮助',
        submenu: [
          {
            label: '在浏览器中打开网易云音乐',
            click: () => shell.openExternal('https://music.163.com')
          }
        ]
      }
    ];
    Menu.setApplicationMenu(Menu.buildFromTemplate(template));
  }

  // ---------- 主窗口 ----------
  function createWindow() {
    mainWindow = new BrowserWindow({
      width: 1280,
      height: 800,
      minWidth: 960,
      minHeight: 600,
      title: APP_NAME,
      icon: path.join(__dirname, 'icon.png'),
      backgroundColor: '#ffffff',
      autoHideMenuBar: true, // 菜单栏默认隐藏,按 Alt 显示
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        spellcheck: false,
        partition: PARTITION
      }
    });

    mainWindow.loadURL(TARGET_URL);

    // 窗口可见时点关闭:最小化驻留(音乐继续播放);
    // 已最小化时再收到关闭请求(部分托盘实现的「退出」发的是关窗消息):真正退出
    mainWindow.on('close', (event) => {
      const minimized = mainWindow.isMinimized();
      log('window close event, isQuitting =', isQuitting, ', minimized =', minimized);
      if (!isQuitting && !minimized) {
        event.preventDefault();
        mainWindow.minimize();
        return;
      }
      isQuitting = true;
    });

    mainWindow.on('closed', () => {
      mainWindow = null;
      if (isQuitting) quitApp(); // 窗口被外部关闭后,确保进程一并退出
    });

    // 站内弹窗用 Electron 新窗口打开;站外链接交给系统默认浏览器
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
      if (/^https?:\/\/(music|st)\.163\.com/.test(url)) {
        return { action: 'allow' };
      }
      shell.openExternal(url);
      return { action: 'deny' };
    });
  }

  app.whenReady().then(() => {
    // 去掉 User-Agent 中的 Electron 标识,按普通 Chrome 浏览器访问
    const ses = session.fromPartition(PARTITION);
    const ua = ses.getUserAgent().replace(/\sElectron\/[\d.]+/, '');
    ses.setUserAgent(ua);
    app.userAgentFallback = ua;

    buildMenu();
    createWindow();
    startControlServer();

    app.on('activate', () => showWindow());
  });

  app.on('before-quit', () => {
    isQuitting = true;
  });

  // 不监听 window-all-closed 自动退出:窗口最小化后应用驻留继续播放
}
