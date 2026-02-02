"""对话框模块"""

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.scrolled import ScrolledText
from tkinter import messagebox, Button
import json

from konata_api.utils import (
    resource_path, save_config,
    is_autostart_enabled, set_autostart
)


class SettingsDialog:
    """设置对话框（分页布局）"""
    def __init__(self, parent, config, app=None):
        self.config = config
        self.app = app  # 主应用引用，用于更新自动查询
        self.dialog = ttk.Toplevel(parent)
        self.dialog.title("⚙️ 设置")
        self.dialog.geometry("550x420")
        self.dialog.resizable(False, False)

        # 设置窗口图标
        try:
            self.dialog.iconbitmap(resource_path("assets/icon.ico"))
        except:
            pass

        # 居中显示
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_settings()

    def create_widgets(self):
        """创建对话框控件"""
        main_frame = ttk.Frame(self.dialog, padding=15)
        main_frame.pack(fill=BOTH, expand=YES)

        # 创建 Notebook 分页
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=BOTH, expand=YES, pady=(0, 15))

        # === 通用设置页 ===
        general_tab = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(general_tab, text="  🔧 通用设置  ")
        self.create_general_tab(general_tab)

        # === API 接口页 ===
        api_tab = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(api_tab, text="  🔗 API 接口  ")
        self.create_api_tab(api_tab)

        # === 自动查询页 ===
        auto_tab = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(auto_tab, text="  ⏰ 自动查询  ")
        self.create_auto_tab(auto_tab)

        # 底部按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=X)

        ttk.Button(btn_frame, text="保存", command=self.save_settings,
                   bootstyle="success", width=12).pack(side=RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.dialog.destroy,
                   bootstyle="secondary", width=12).pack(side=RIGHT, padx=5)

    def create_general_tab(self, parent):
        """创建通用设置页"""
        # 开机自启动
        autostart_frame = ttk.Labelframe(parent, text=" 启动选项 ", padding=15)
        autostart_frame.pack(fill=X, pady=(0, 15))

        self.autostart_var = ttk.BooleanVar()
        ttk.Checkbutton(
            autostart_frame,
            text="开机自动启动",
            variable=self.autostart_var,
            bootstyle="round-toggle"
        ).pack(anchor=W)
        ttk.Label(
            autostart_frame,
            text="启用后程序将在 Windows 启动时自动运行",
            font=("Microsoft YaHei", 9),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(5, 0))

        # 窗口行为
        window_frame = ttk.Labelframe(parent, text=" 窗口行为 ", padding=15)
        window_frame.pack(fill=X)

        self.minimize_to_tray_var = ttk.BooleanVar(value=True)
        ttk.Checkbutton(
            window_frame,
            text="关闭窗口时最小化到托盘",
            variable=self.minimize_to_tray_var,
            bootstyle="round-toggle"
        ).pack(anchor=W)
        ttk.Label(
            window_frame,
            text="禁用后点击关闭按钮将直接退出程序",
            font=("Microsoft YaHei", 9),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(5, 0))

    def create_api_tab(self, parent):
        """创建 API 接口设置页"""
        ttk.Label(
            parent,
            text="自定义 API 接口路径（留空使用默认值）",
            font=("Microsoft YaHei", 9),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(0, 15))

        # 余额订阅接口
        sub_frame = ttk.Frame(parent)
        sub_frame.pack(fill=X, pady=5)
        ttk.Label(sub_frame, text="余额订阅接口:", width=14).pack(side=LEFT)
        self.sub_var = ttk.StringVar()
        ttk.Entry(sub_frame, textvariable=self.sub_var, bootstyle="info").pack(side=LEFT, fill=X, expand=YES)

        # 余额用量接口
        usage_frame = ttk.Frame(parent)
        usage_frame.pack(fill=X, pady=5)
        ttk.Label(usage_frame, text="余额用量接口:", width=14).pack(side=LEFT)
        self.usage_var = ttk.StringVar()
        ttk.Entry(usage_frame, textvariable=self.usage_var, bootstyle="info").pack(side=LEFT, fill=X, expand=YES)

        # 日志查询接口
        logs_frame = ttk.Frame(parent)
        logs_frame.pack(fill=X, pady=5)
        ttk.Label(logs_frame, text="日志查询接口:", width=14).pack(side=LEFT)
        self.logs_var = ttk.StringVar()
        ttk.Entry(logs_frame, textvariable=self.logs_var, bootstyle="info").pack(side=LEFT, fill=X, expand=YES)

        # 日志每页条数
        page_size_frame = ttk.Frame(parent)
        page_size_frame.pack(fill=X, pady=5)
        ttk.Label(page_size_frame, text="日志每页条数:", width=14).pack(side=LEFT)
        self.page_size_var = ttk.StringVar()
        ttk.Entry(page_size_frame, textvariable=self.page_size_var, width=10, bootstyle="info").pack(side=LEFT)
        ttk.Label(page_size_frame, text="（默认 50）", bootstyle="secondary").pack(side=LEFT, padx=(10, 0))

        # 恢复默认按钮
        ttk.Button(
            parent,
            text="恢复默认接口",
            command=self.reset_api_defaults,
            bootstyle="warning-outline",
            width=15
        ).pack(anchor=W, pady=(20, 0))

    def create_auto_tab(self, parent):
        """创建自动查询设置页"""
        # 启用开关
        enable_frame = ttk.Labelframe(parent, text=" 自动批量查询 ", padding=15)
        enable_frame.pack(fill=X, pady=(0, 15))

        self.auto_query_var = ttk.BooleanVar()
        ttk.Checkbutton(
            enable_frame,
            text="启用自动批量查询",
            variable=self.auto_query_var,
            bootstyle="round-toggle",
            command=self.on_auto_query_toggle
        ).pack(anchor=W)
        ttk.Label(
            enable_frame,
            text="启用后将按设定的时间间隔自动查询所有站点余额",
            font=("Microsoft YaHei", 9),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(5, 0))

        # 查询间隔
        interval_frame = ttk.Labelframe(parent, text=" 查询间隔 ", padding=15)
        interval_frame.pack(fill=X)

        interval_input_frame = ttk.Frame(interval_frame)
        interval_input_frame.pack(fill=X)

        ttk.Label(interval_input_frame, text="每隔").pack(side=LEFT)
        self.interval_var = ttk.StringVar(value="30")
        self.interval_entry = ttk.Entry(
            interval_input_frame,
            textvariable=self.interval_var,
            width=8,
            bootstyle="info"
        )
        self.interval_entry.pack(side=LEFT, padx=8)
        ttk.Label(interval_input_frame, text="分钟自动查询一次").pack(side=LEFT)

        ttk.Label(
            interval_frame,
            text="建议设置 30 分钟以上，避免频繁请求",
            font=("Microsoft YaHei", 9),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(10, 0))

    def on_auto_query_toggle(self):
        """自动查询开关切换"""
        enabled = self.auto_query_var.get()
        state = "normal" if enabled else "disabled"
        self.interval_entry.configure(state=state)

    def load_settings(self):
        """加载当前设置"""
        # 通用设置
        self.autostart_var.set(is_autostart_enabled())
        self.minimize_to_tray_var.set(self.config.get("minimize_to_tray", True))

        # API 接口
        endpoints = self.config.get("api_endpoints", {})
        self.sub_var.set(endpoints.get("balance_subscription", "/v1/dashboard/billing/subscription"))
        self.usage_var.set(endpoints.get("balance_usage", "/v1/dashboard/billing/usage"))
        self.logs_var.set(endpoints.get("logs", "/api/log/token"))
        self.page_size_var.set(str(endpoints.get("logs_page_size", 50)))

        # 自动查询
        auto_query = self.config.get("auto_query", {})
        self.auto_query_var.set(auto_query.get("enabled", False))
        self.interval_var.set(str(auto_query.get("interval_minutes", 30)))
        self.on_auto_query_toggle()  # 更新输入框状态

    def reset_api_defaults(self):
        """恢复默认 API 设置"""
        self.sub_var.set("/v1/dashboard/billing/subscription")
        self.usage_var.set("/v1/dashboard/billing/usage")
        self.logs_var.set("/api/log/token")
        self.page_size_var.set("50")

    def save_settings(self):
        """保存所有设置"""
        # 保存开机自启动
        set_autostart(self.autostart_var.get())

        # 保存最小化到托盘设置
        self.config["minimize_to_tray"] = self.minimize_to_tray_var.get()

        # 保存 API 接口设置
        try:
            page_size = int(self.page_size_var.get().strip())
            if page_size <= 0:
                page_size = 50
        except ValueError:
            page_size = 50

        self.config["api_endpoints"] = {
            "balance_subscription": self.sub_var.get().strip(),
            "balance_usage": self.usage_var.get().strip(),
            "logs": self.logs_var.get().strip(),
            "logs_page_size": page_size
        }

        # 保存自动查询设置
        try:
            interval = int(self.interval_var.get().strip())
            if interval < 1:
                interval = 30
        except ValueError:
            interval = 30

        self.config["auto_query"] = {
            "enabled": self.auto_query_var.get(),
            "interval_minutes": interval
        }

        save_config(self.config)

        # 通知主应用更新自动查询
        if self.app:
            self.app.update_auto_query()

        messagebox.showinfo("成功", "设置已保存", parent=self.dialog)
        self.dialog.destroy()


class RawResponseDialog:
    """原始返回数据查看弹窗"""
    def __init__(self, parent, title, data):
        self.dialog = ttk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("700x500")
        self.dialog.resizable(True, True)

        # 设置窗口图标
        try:
            self.dialog.iconbitmap(resource_path("assets/icon.ico"))
        except:
            pass

        # 居中显示
        self.dialog.transient(parent)

        self.create_widgets(data)

    def create_widgets(self, data):
        """创建弹窗控件"""
        main_frame = ttk.Frame(self.dialog, padding=15)
        main_frame.pack(fill=BOTH, expand=YES)

        ttk.Label(main_frame, text="API 返回的原始 JSON 数据：", font=("Microsoft YaHei", 10)).pack(anchor=W, pady=(0, 10))

        # JSON 文本框
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=BOTH, expand=YES)

        self.text = ScrolledText(text_frame, font=("Consolas", 10), wrap="none", autohide=True)
        self.text.pack(fill=BOTH, expand=YES)

        # 格式化 JSON 并显示
        try:
            formatted_json = json.dumps(data, ensure_ascii=False, indent=2)
        except:
            formatted_json = str(data)

        self.text.insert("1.0", formatted_json)

        # 按钮区
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=X, pady=(15, 0))

        ttk.Button(btn_frame, text="📋 复制到剪贴板", command=self.copy_to_clipboard, bootstyle="info-outline", width=15).pack(side=LEFT)
        ttk.Button(btn_frame, text="关闭", command=self.dialog.destroy, bootstyle="secondary", width=10).pack(side=RIGHT)

    def copy_to_clipboard(self):
        """复制内容到剪贴板"""
        content = self.text.get("1.0", "end-1c")
        self.dialog.clipboard_clear()
        self.dialog.clipboard_append(content)
        messagebox.showinfo("成功", "已复制到剪贴板", parent=self.dialog)
