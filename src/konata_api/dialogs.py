"""对话框模块"""

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledFrame
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
        self.dialog.geometry("550x600")
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
        window_frame.pack(fill=X, pady=(0, 15))

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

        # 余额提醒
        balance_frame = ttk.Labelframe(parent, text=" 余额提醒 ", padding=15)
        balance_frame.pack(fill=X, pady=(0, 15))

        threshold_row = ttk.Frame(balance_frame)
        threshold_row.pack(fill=X)
        ttk.Label(threshold_row, text="低余额阈值:").pack(side=LEFT)
        self.threshold_var = ttk.StringVar()
        ttk.Entry(threshold_row, textvariable=self.threshold_var, width=10, bootstyle="info").pack(side=LEFT, padx=(10, 0))
        ttk.Label(threshold_row, text="USD（默认 10）", bootstyle="secondary").pack(side=LEFT, padx=(10, 0))
        ttk.Label(
            balance_frame,
            text="批量查询时，余额低于此值的站点将显示警告",
            font=("Microsoft YaHei", 9),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(5, 0))

        # 日志设置
        logs_frame = ttk.Labelframe(parent, text=" 日志设置 ", padding=15)
        logs_frame.pack(fill=X)

        page_size_row = ttk.Frame(logs_frame)
        page_size_row.pack(fill=X)
        ttk.Label(page_size_row, text="日志每页条数:").pack(side=LEFT)
        self.page_size_var = ttk.StringVar()
        ttk.Entry(page_size_row, textvariable=self.page_size_var, width=10, bootstyle="info").pack(side=LEFT, padx=(10, 0))
        ttk.Label(page_size_row, text="（默认 50）", bootstyle="secondary").pack(side=LEFT, padx=(10, 0))

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

        # 余额提醒
        self.threshold_var.set(str(self.config.get("low_balance_threshold", 10)))

        # 日志设置
        endpoints = self.config.get("api_endpoints", {})
        self.page_size_var.set(str(endpoints.get("logs_page_size", 50)))

        # 自动查询
        auto_query = self.config.get("auto_query", {})
        self.auto_query_var.set(auto_query.get("enabled", False))
        self.interval_var.set(str(auto_query.get("interval_minutes", 30)))
        self.on_auto_query_toggle()  # 更新输入框状态

    def save_settings(self):
        """保存所有设置"""
        # 保存开机自启动
        set_autostart(self.autostart_var.get())

        # 保存最小化到托盘设置
        self.config["minimize_to_tray"] = self.minimize_to_tray_var.get()

        # 保存低余额阈值
        try:
            threshold = float(self.threshold_var.get().strip())
            if threshold < 0:
                threshold = 10
        except ValueError:
            threshold = 10
        self.config["low_balance_threshold"] = threshold

        # 保存日志设置（保留原有的 api_endpoints，只更新 page_size）
        try:
            page_size = int(self.page_size_var.get().strip())
            if page_size <= 0:
                page_size = 50
        except ValueError:
            page_size = 50

        if "api_endpoints" not in self.config:
            self.config["api_endpoints"] = {}
        self.config["api_endpoints"]["logs_page_size"] = page_size

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

        # JSON 文本框（带横向和纵向滚动条）
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=BOTH, expand=YES)

        # 创建滚动条
        x_scrollbar = ttk.Scrollbar(text_frame, orient="horizontal")
        y_scrollbar = ttk.Scrollbar(text_frame, orient="vertical")

        self.text = ttk.Text(
            text_frame,
            font=("Consolas", 10),
            wrap="none",
            xscrollcommand=x_scrollbar.set,
            yscrollcommand=y_scrollbar.set
        )

        x_scrollbar.config(command=self.text.xview)
        y_scrollbar.config(command=self.text.yview)

        # 布局
        x_scrollbar.pack(side=BOTTOM, fill=X)
        y_scrollbar.pack(side=RIGHT, fill=Y)
        self.text.pack(side=LEFT, fill=BOTH, expand=YES)

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


class ProfileAdvancedDialog:
    """站点高级设置对话框（auth_type、endpoints、proxy、jwt_token）"""
    def __init__(self, parent, profile, on_save_callback):
        self.profile = profile
        self.on_save_callback = on_save_callback
        self.dialog = ttk.Toplevel(parent)
        self.dialog.title(f"⚙️ 高级设置 - {profile.get('name', '未命名')}")
        self.dialog.geometry("550x500")
        self.dialog.resizable(False, True)

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
        # 外层容器
        outer_frame = ttk.Frame(self.dialog, padding=10)
        outer_frame.pack(fill=BOTH, expand=YES)

        # 滚动容器
        scroll_frame = ScrolledFrame(outer_frame, autohide=True)
        scroll_frame.pack(fill=BOTH, expand=YES)

        # 内容区域
        main_frame = scroll_frame

        # === 余额查询认证方式 ===
        balance_auth_frame = ttk.Labelframe(main_frame, text=" 余额查询认证方式 ", padding=10)
        balance_auth_frame.pack(fill=X, pady=(0, 10), padx=5)

        self.balance_auth_type_var = ttk.StringVar(value="bearer")
        ttk.Radiobutton(
            balance_auth_frame,
            text="Bearer Token (Header 认证)",
            variable=self.balance_auth_type_var,
            value="bearer",
            bootstyle="info"
        ).pack(anchor=W, pady=2)
        ttk.Radiobutton(
            balance_auth_frame,
            text="URL Key (URL 参数认证)",
            variable=self.balance_auth_type_var,
            value="url_key",
            bootstyle="info"
        ).pack(anchor=W, pady=2)
        ttk.Label(
            balance_auth_frame,
            text="大多数站点余额查询使用 Bearer 认证",
            font=("Microsoft YaHei", 9),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(3, 0))

        # === 日志查询认证方式 ===
        log_auth_frame = ttk.Labelframe(main_frame, text=" 日志查询认证方式 ", padding=10)
        log_auth_frame.pack(fill=X, pady=(0, 10), padx=5)

        self.log_auth_type_var = ttk.StringVar(value="url_key")
        ttk.Radiobutton(
            log_auth_frame,
            text="Bearer Token (Header 认证)",
            variable=self.log_auth_type_var,
            value="bearer",
            bootstyle="info"
        ).pack(anchor=W, pady=2)
        ttk.Radiobutton(
            log_auth_frame,
            text="URL Key (URL 参数认证)",
            variable=self.log_auth_type_var,
            value="url_key",
            bootstyle="info"
        ).pack(anchor=W, pady=2)
        ttk.Label(
            log_auth_frame,
            text="大多数站点日志查询使用 URL Key 认证（?key=xxx）",
            font=("Microsoft YaHei", 9),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(3, 0))

        # === JWT Token（用于 sub2api 等需要登录态的站点）===
        jwt_frame = ttk.Labelframe(main_frame, text=" JWT Token（可选）", padding=10)
        jwt_frame.pack(fill=X, pady=(0, 10), padx=5)

        ttk.Label(
            jwt_frame,
            text="部分站点（如 sub2api）的日志接口需要 JWT Token 认证",
            font=("Microsoft YaHei", 9),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(0, 5))

        self.jwt_token_var = ttk.StringVar()
        ttk.Entry(jwt_frame, textvariable=self.jwt_token_var, bootstyle="info", show="*").pack(fill=X)

        ttk.Label(
            jwt_frame,
            text="从浏览器登录后获取，格式为 eyJxxx...（会过期）",
            font=("Microsoft YaHei", 9),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(3, 0))

        # === 日志代理 ===
        proxy_frame = ttk.Labelframe(main_frame, text=" 日志代理（可选）", padding=10)
        proxy_frame.pack(fill=X, pady=(0, 10), padx=5)

        ttk.Label(
            proxy_frame,
            text="部分站点的日志接口有访问限制，需要通过代理访问",
            font=("Microsoft YaHei", 9),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(0, 5))

        self.proxy_var = ttk.StringVar()
        ttk.Entry(proxy_frame, textvariable=self.proxy_var, bootstyle="info").pack(fill=X)

        ttk.Label(
            proxy_frame,
            text="例如: https://proxy.cifang.xyz/proxy",
            font=("Microsoft YaHei", 9),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(3, 0))

        # === 自定义接口路径 ===
        endpoints_frame = ttk.Labelframe(main_frame, text=" 自定义接口路径（留空使用默认）", padding=10)
        endpoints_frame.pack(fill=X, pady=(0, 10), padx=5)

        # 余额订阅接口
        sub_frame = ttk.Frame(endpoints_frame)
        sub_frame.pack(fill=X, pady=2)
        ttk.Label(sub_frame, text="余额订阅:", width=10).pack(side=LEFT)
        self.sub_var = ttk.StringVar()
        ttk.Entry(sub_frame, textvariable=self.sub_var, bootstyle="info").pack(side=LEFT, fill=X, expand=YES)

        # 余额用量接口
        usage_frame = ttk.Frame(endpoints_frame)
        usage_frame.pack(fill=X, pady=2)
        ttk.Label(usage_frame, text="余额用量:", width=10).pack(side=LEFT)
        self.usage_var = ttk.StringVar()
        ttk.Entry(usage_frame, textvariable=self.usage_var, bootstyle="info").pack(side=LEFT, fill=X, expand=YES)

        # 日志查询接口
        logs_frame = ttk.Frame(endpoints_frame)
        logs_frame.pack(fill=X, pady=2)
        ttk.Label(logs_frame, text="日志查询:", width=10).pack(side=LEFT)
        self.logs_var = ttk.StringVar()
        ttk.Entry(logs_frame, textvariable=self.logs_var, bootstyle="info").pack(side=LEFT, fill=X, expand=YES)

        # 底部按钮（放在滚动区域外）
        btn_frame = ttk.Frame(outer_frame)
        btn_frame.pack(fill=X, pady=(10, 0))

        ttk.Button(btn_frame, text="保存", command=self.save_settings,
                   bootstyle="success", width=12).pack(side=RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.dialog.destroy,
                   bootstyle="secondary", width=12).pack(side=RIGHT, padx=5)
        ttk.Button(btn_frame, text="清空自定义", command=self.clear_all,
                   bootstyle="warning-outline", width=12).pack(side=LEFT)

    def load_settings(self):
        """加载当前设置"""
        # 向后兼容：旧配置只有 auth_type，映射到两个字段
        old_auth_type = self.profile.get("auth_type", "bearer")
        self.balance_auth_type_var.set(self.profile.get("balance_auth_type", old_auth_type))
        self.log_auth_type_var.set(self.profile.get("log_auth_type", "url_key"))
        self.jwt_token_var.set(self.profile.get("jwt_token", ""))
        self.proxy_var.set(self.profile.get("proxy", ""))

        endpoints = self.profile.get("endpoints", {})
        self.sub_var.set(endpoints.get("balance_subscription", ""))
        self.usage_var.set(endpoints.get("balance_usage", ""))
        self.logs_var.set(endpoints.get("logs", ""))

    def clear_all(self):
        """清空所有自定义设置"""
        self.jwt_token_var.set("")
        self.proxy_var.set("")
        self.sub_var.set("")
        self.usage_var.set("")
        self.logs_var.set("")

    def save_settings(self):
        """保存设置"""
        self.profile["balance_auth_type"] = self.balance_auth_type_var.get()
        self.profile["log_auth_type"] = self.log_auth_type_var.get()
        # 移除旧的 auth_type 字段（如果存在）
        if "auth_type" in self.profile:
            del self.profile["auth_type"]

        # 保存 JWT Token（非空时）
        jwt_token = self.jwt_token_var.get().strip()
        if jwt_token:
            self.profile["jwt_token"] = jwt_token
        elif "jwt_token" in self.profile:
            del self.profile["jwt_token"]

        # 保存日志代理（非空时）
        proxy = self.proxy_var.get().strip()
        if proxy:
            self.profile["proxy"] = proxy
        elif "proxy" in self.profile:
            del self.profile["proxy"]

        # 只保存非空的 endpoints
        endpoints = {}
        if self.sub_var.get().strip():
            endpoints["balance_subscription"] = self.sub_var.get().strip()
        if self.usage_var.get().strip():
            endpoints["balance_usage"] = self.usage_var.get().strip()
        if self.logs_var.get().strip():
            endpoints["logs"] = self.logs_var.get().strip()

        if endpoints:
            self.profile["endpoints"] = endpoints
        elif "endpoints" in self.profile:
            del self.profile["endpoints"]

        # 回调保存
        if self.on_save_callback:
            self.on_save_callback(self.profile)

        messagebox.showinfo("成功", "高级设置已保存", parent=self.dialog)
        self.dialog.destroy()


class BalanceSummaryDialog:
    """批量查询汇总统计对话框"""
    def __init__(self, parent, summary_data, low_balance_threshold=10):
        """
        summary_data 格式:
        {
            "success": 5,
            "failed": 1,
            "skipped": 0,
            "sites": [
                {"name": "站点A", "balance": 45.0, "unit": "USD", "today_cost": 1.23, "error": None},
                {"name": "站点B", "balance": 50000, "unit": "Token", "today_cost": 0, "error": None},
                {"name": "站点C", "balance": 0, "unit": "", "today_cost": 0, "error": "连接超时"},
            ]
        }
        """
        self.summary_data = summary_data
        self.threshold = low_balance_threshold
        self.dialog = ttk.Toplevel(parent)
        self.dialog.title("📊 批量查询汇总统计")
        self.dialog.geometry("600x550")
        self.dialog.resizable(True, True)

        # 设置窗口图标
        try:
            self.dialog.iconbitmap(resource_path("assets/icon.ico"))
        except:
            pass

        # 居中显示
        self.dialog.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        """创建弹窗控件"""
        main_frame = ttk.Frame(self.dialog, padding=15)
        main_frame.pack(fill=BOTH, expand=YES)

        # === 站点统计 ===
        stats_frame = ttk.Labelframe(main_frame, text=" 站点统计 ", padding=10)
        stats_frame.pack(fill=X, pady=(0, 10))

        success = self.summary_data.get("success", 0)
        failed = self.summary_data.get("failed", 0)
        skipped = self.summary_data.get("skipped", 0)
        total = success + failed + skipped

        stats_text = f"✅ 成功: {success}    ❌ 失败: {failed}    ⚠️ 跳过: {skipped}    📊 总计: {total}"
        ttk.Label(stats_frame, text=stats_text, font=("Microsoft YaHei", 10)).pack(anchor=W)

        # === 各站点详情表格 ===
        detail_frame = ttk.Labelframe(main_frame, text=" 各站点详情 ", padding=10)
        detail_frame.pack(fill=BOTH, expand=YES, pady=(0, 10))

        columns = ("name", "balance", "today_cost", "status")
        self.detail_tree = ttk.Treeview(detail_frame, columns=columns, show="headings", height=10, bootstyle="info")
        self.detail_tree.heading("name", text="站点名称")
        self.detail_tree.heading("balance", text="余额")
        self.detail_tree.heading("today_cost", text="今日消耗")
        self.detail_tree.heading("status", text="状态")

        self.detail_tree.column("name", width=150)
        self.detail_tree.column("balance", width=120)
        self.detail_tree.column("today_cost", width=100)
        self.detail_tree.column("status", width=100)

        # 滚动条
        scrollbar = ttk.Scrollbar(detail_frame, orient="vertical", command=self.detail_tree.yview)
        self.detail_tree.configure(yscrollcommand=scrollbar.set)
        self.detail_tree.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)

        # 填充数据
        self.populate_detail_tree()

        # === 汇总统计 ===
        summary_frame = ttk.Labelframe(main_frame, text=" 汇总 ", padding=10)
        summary_frame.pack(fill=X, pady=(0, 10))

        totals = self.calculate_totals()
        summary_lines = []

        # 按币种显示总余额
        for unit, amount in totals["balance_by_unit"].items():
            if unit == "USD" or unit == "CNY" or unit == "":
                symbol = "$" if unit == "USD" else ("¥" if unit == "CNY" else "$")
                summary_lines.append(f"💵 总余额 {unit or 'USD'}: {symbol}{amount:,.2f}")
            elif unit == "Token":
                summary_lines.append(f"🎫 总余额 Token: {self.fmt_num(amount)}")
            else:
                summary_lines.append(f"💰 总余额 {unit}: {amount:,.2f}")

        # 总消耗
        if totals["total_today_cost"] > 0:
            summary_lines.append(f"📊 今日总消耗: ${totals['total_today_cost']:,.2f}")

        for line in summary_lines:
            ttk.Label(summary_frame, text=line, font=("Microsoft YaHei", 10)).pack(anchor=W, pady=2)

        if not summary_lines:
            ttk.Label(summary_frame, text="暂无汇总数据", font=("Microsoft YaHei", 10), bootstyle="secondary").pack(anchor=W)

        # === 低余额警告 ===
        low_balance_sites = self.get_low_balance_sites()
        if low_balance_sites:
            warning_frame = ttk.Labelframe(main_frame, text=f" ⚠️ 低余额警告 (阈值: ${self.threshold}) ", padding=10, bootstyle="warning")
            warning_frame.pack(fill=X, pady=(0, 10))

            for site in low_balance_sites:
                ttk.Label(
                    warning_frame,
                    text=f"• {site['name']}: ${site['balance']:.2f}",
                    font=("Microsoft YaHei", 10),
                    bootstyle="warning"
                ).pack(anchor=W)

        # === 底部按钮 ===
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=X)

        ttk.Button(btn_frame, text="关闭", command=self.dialog.destroy, bootstyle="secondary", width=12).pack(side=RIGHT)

    def populate_detail_tree(self):
        """填充站点详情表格"""
        sites = self.summary_data.get("sites", [])

        for site in sites:
            name = site.get("name", "未命名")
            balance = site.get("balance", 0)
            unit = site.get("unit", "USD")
            today_cost = site.get("today_cost", 0)
            error = site.get("error")

            # 格式化余额
            if error:
                balance_str = "-"
                status = "❌ 失败"
            elif unit == "Token":
                balance_str = self.fmt_num(balance)
                status = "✅ 成功"
            else:
                symbol = "$" if unit in ("USD", "") else ("¥" if unit == "CNY" else "")
                balance_str = f"{symbol}{balance:,.2f}" if balance else "-"
                status = "✅ 成功" if balance or balance == 0 else "⚠️ 无数据"

            # 格式化今日消耗
            today_cost_str = f"${today_cost:.2f}" if today_cost > 0 else "-"

            # 低余额标记
            if not error and unit in ("USD", "CNY", "") and balance < self.threshold and balance > 0:
                name = f"⚠️ {name}"

            self.detail_tree.insert("", "end", values=(name, balance_str, today_cost_str, status))

    def calculate_totals(self):
        """计算汇总数据"""
        balance_by_unit = {}
        total_today_cost = 0

        for site in self.summary_data.get("sites", []):
            if site.get("error"):
                continue

            balance = site.get("balance", 0)
            unit = site.get("unit", "USD") or "USD"
            today_cost = site.get("today_cost", 0)

            if balance:
                balance_by_unit[unit] = balance_by_unit.get(unit, 0) + balance

            if today_cost:
                total_today_cost += today_cost

        return {
            "balance_by_unit": balance_by_unit,
            "total_today_cost": total_today_cost
        }

    def get_low_balance_sites(self):
        """获取低余额站点列表"""
        low_sites = []
        for site in self.summary_data.get("sites", []):
            if site.get("error"):
                continue
            unit = site.get("unit", "USD")
            balance = site.get("balance", 0)
            # 只对 USD/CNY 类型判断低余额
            if unit in ("USD", "CNY", "") and 0 < balance < self.threshold:
                low_sites.append(site)
        return sorted(low_sites, key=lambda x: x.get("balance", 0))

    def fmt_num(self, n):
        """格式化大数字"""
        if n >= 1_000_000_000:
            return f"{n/1_000_000_000:.1f}B"
        elif n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        elif n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(int(n))
