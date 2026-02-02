"""系统托盘模块"""

import threading
from PIL import Image
import pystray
from pystray import MenuItem as Item

from konata_api.utils import resource_path


class TrayIcon:
    """系统托盘图标管理"""

    def __init__(self, app):
        """
        初始化托盘图标

        Args:
            app: ApiQueryApp 实例，用于回调主窗口方法
        """
        self.app = app
        self.icon = None
        self._running = False

    def create_menu(self):
        """创建右键菜单"""
        return pystray.Menu(
            Item("📌 显示主窗口", self.on_show_window, default=True),
            Item("🔄 查询全部余额", self.on_query_all),
            pystray.Menu.SEPARATOR,
            Item("⚙️ 设置", self.on_open_settings),
            pystray.Menu.SEPARATOR,
            Item("❌ 退出程序", self.on_quit)
        )

    def create_icon(self):
        """创建托盘图标"""
        try:
            image = Image.open(resource_path("assets/icon.ico"))
        except Exception:
            # 如果图标加载失败，创建一个简单的默认图标
            image = Image.new('RGB', (64, 64), color='#3498db')

        self.icon = pystray.Icon(
            name="KonataAPI",
            icon=image,
            title="此方API查查",
            menu=self.create_menu()
        )
        return self.icon

    def run(self):
        """在后台线程运行托盘图标"""
        if self._running:
            return

        self._running = True
        self.create_icon()

        # 在单独的线程中运行托盘
        tray_thread = threading.Thread(target=self.icon.run, daemon=True)
        tray_thread.start()

    def stop(self):
        """停止托盘图标"""
        if self.icon and self._running:
            self.icon.stop()
            self._running = False

    # === 菜单回调 ===

    def on_show_window(self, icon=None, item=None):
        """显示主窗口"""
        self.app.root.after(0, self.app.show_window)

    def on_query_all(self, icon=None, item=None):
        """查询全部余额"""
        self.app.root.after(0, self.app.show_window)
        self.app.root.after(100, self.app.query_all_balance)

    def on_open_settings(self, icon=None, item=None):
        """打开设置"""
        self.app.root.after(0, self.app.show_window)
        self.app.root.after(100, self.app.open_settings)

    def on_quit(self, icon=None, item=None):
        """退出程序"""
        self.stop()
        self.app.root.after(0, self.app.quit_app)
