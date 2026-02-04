"""主应用模块"""

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.scrolled import ScrolledText
from tkinter import messagebox
from tkinter import Label as TkLabel
from PIL import Image, ImageTk
import json
import os
import threading
from datetime import datetime

from konata_api.api import query_balance, query_logs, do_checkin, query_balance_by_cookie
from konata_api.utils import (
    get_exe_dir, resource_path, load_config, save_config
)
from konata_api.dialogs import SettingsDialog, RawResponseDialog, BalanceSummaryDialog, ProfileAdvancedDialog
from konata_api.tray import TrayIcon
from konata_api.stats_dialog import StatsFrame
from konata_api.stats import load_stats, save_stats, get_site_by_id, add_checkin_log, update_site, load_checkin_log
from konata_api.test_dialog import TestFrame


class ApiQueryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("此方API查查")
        self.root.geometry("1100x750")
        self.root.minsize(950, 700)

        # 设置窗口图标
        try:
            self.root.iconbitmap(resource_path("assets/icon.ico"))
        except:
            pass

        # 加载配置
        self.config = load_config()

        # 保存最近一次的原始返回数据（内存缓存）
        self.last_raw_response = {"balance": None, "logs": None}

        # 原始数据保存文件路径
        self.raw_response_file = os.path.join(get_exe_dir(), "config", "raw_response.json")

        # 创建界面
        self.create_widgets()

        # 刷新配置列表
        self.refresh_profile_list()

        # 初始化系统托盘
        self.tray = TrayIcon(self)
        self.tray.run()

        # 重写窗口关闭行为
        self.root.protocol("WM_DELETE_WINDOW", self.on_close_window)

        # 自动查询定时器 ID
        self._auto_query_timer_id = None
        self.start_auto_query()

    def create_widgets(self):
        # 创建背景 Label
        self.create_background()

        # 主框架
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.place(x=20, y=20, relwidth=1, relheight=1, width=-40, height=-40)

        # === 左侧：中转站列表（数据源：stats.json） ===
        left_frame = ttk.Labelframe(main_frame, text=" 中转站列表 ", padding=15, bootstyle="info")
        left_frame.pack(side=LEFT, fill=Y, padx=(0, 15))

        # 站点列表 Treeview
        columns = ("name", "balance")
        self.profile_tree = ttk.Treeview(left_frame, columns=columns, show="headings", height=18, bootstyle="info")
        self.profile_tree.heading("name", text="名称", command=lambda: self.sort_profile_list("name"))
        self.profile_tree.heading("balance", text="余额 ↓", command=lambda: self.sort_profile_list("balance"))
        self.profile_tree.column("name", width=140)
        self.profile_tree.column("balance", width=120)
        self.profile_tree.pack(fill=BOTH, expand=YES)
        self.profile_tree.bind("<<TreeviewSelect>>", self.on_profile_select)

        # 排序状态：字段名 + 是否降序
        self._sort_key = "balance"
        self._sort_reverse = True

        # 列表操作按钮
        list_btn_frame = ttk.Frame(left_frame)
        list_btn_frame.pack(fill=X, pady=(15, 0))
        ttk.Button(list_btn_frame, text="➕ 添加站点", command=self.add_site_from_list, bootstyle="success-outline", width=20).pack(fill=X, pady=3)
        ttk.Button(list_btn_frame, text="🔄 刷新列表", command=self.refresh_profile_list, bootstyle="secondary-outline", width=20).pack(fill=X, pady=3)
        ttk.Button(list_btn_frame, text="💰 查询全部余额", command=self.query_all_balance, bootstyle="info-outline", width=20).pack(fill=X, pady=3)
        ttk.Button(list_btn_frame, text="🍪 Cookie查余额并保存", command=self.query_all_balance_by_cookie_and_save, bootstyle="success-outline", width=20).pack(fill=X, pady=3)
        ttk.Button(list_btn_frame, text="🎁 一键签到", command=self.open_all_checkin_from_list, bootstyle="warning-outline", width=20).pack(fill=X, pady=3)
        ttk.Button(list_btn_frame, text="📋 签到记录", command=self.show_checkin_log, bootstyle="secondary-outline", width=20).pack(fill=X, pady=3)
        ttk.Button(list_btn_frame, text="🗑️ 删除选中", command=self.delete_site_from_list, bootstyle="danger-outline", width=20).pack(fill=X, pady=3)

        # === 右侧：主 Notebook 标签页 ===
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=LEFT, fill=BOTH, expand=YES)

        # === 标题栏 ===
        title_frame = ttk.Frame(right_frame)
        title_frame.pack(fill=X, pady=(0, 10))

        title_left = ttk.Frame(title_frame)
        title_left.pack(side=LEFT, fill=X, expand=YES)
        ttk.Label(title_left, text="此方API查查", font=("Microsoft YaHei", 16, "bold"), bootstyle="inverse-primary").pack(anchor=W)
        ttk.Label(title_left, text="支持多中转站配置管理与批量查询", font=("Microsoft YaHei", 9), bootstyle="secondary").pack(anchor=W)

        ttk.Button(title_frame, text="⚙️ 设置", command=self.open_settings, bootstyle="secondary-outline", width=10).pack(side=RIGHT, padx=5)

        # === 主功能 Notebook ===
        # 自定义标签页样式 - 更大的字体和 padding
        style = ttk.Style()
        style.configure("Big.TNotebook.Tab", font=("Microsoft YaHei", 11, "bold"), padding=(20, 10))

        self.main_notebook = ttk.Notebook(right_frame, bootstyle="primary", style="Big.TNotebook")
        self.main_notebook.pack(fill=BOTH, expand=YES)

        # Tab 1: 数据统计
        stats_tab = ttk.Frame(self.main_notebook, padding=5)
        self.main_notebook.add(stats_tab, text="  📊 数据统计  ")
        self.stats_frame = StatsFrame(stats_tab, profiles=self.config.get("profiles", []), show_site_list=False, on_save_callback=self.on_stats_save)
        self.stats_frame.pack(fill=BOTH, expand=YES)

        # Tab 2: 余额查询
        query_tab = ttk.Frame(self.main_notebook, padding=5)
        self.main_notebook.add(query_tab, text="  💰 余额查询  ")
        self.create_query_tab(query_tab)

        # Tab 3: 站点测试
        test_tab = ttk.Frame(self.main_notebook, padding=5)
        self.main_notebook.add(test_tab, text="  🧪 站点测试  ")
        self.test_frame = TestFrame(test_tab, show_site_list=False)
        self.test_frame.pack(fill=BOTH, expand=YES)

        # === 状态栏 ===
        self.status_var = ttk.StringVar(value="就绪 - 双击左侧列表选择配置，或手动输入新配置")
        status_bar = ttk.Label(right_frame, textvariable=self.status_var, bootstyle="inverse-secondary", padding=(10, 5))
        status_bar.pack(fill=X, pady=(10, 0))

    def create_query_tab(self, parent):
        """创建查询标签页内容"""
        # === 配置详情区 ===
        config_frame = ttk.Labelframe(parent, text=" 配置详情 ", padding=15, bootstyle="primary")
        config_frame.pack(fill=X, pady=(0, 10))

        # 配置名称
        name_frame = ttk.Frame(config_frame)
        name_frame.pack(fill=X, pady=5)
        ttk.Label(name_frame, text="配置名称:", width=12).pack(side=LEFT)
        self.name_var = ttk.StringVar()
        ttk.Entry(name_frame, textvariable=self.name_var, width=25, bootstyle="info", state="readonly").pack(side=LEFT, padx=(0, 10))
        ttk.Button(name_frame, text="⚙️ 高级设置", command=self.open_profile_advanced, bootstyle="secondary-outline", width=12).pack(side=RIGHT)

        # Base URL
        url_frame = ttk.Frame(config_frame)
        url_frame.pack(fill=X, pady=5)
        ttk.Label(url_frame, text="Base URL:", width=12).pack(side=LEFT)
        self.url_var = ttk.StringVar()
        ttk.Entry(url_frame, textvariable=self.url_var, bootstyle="info").pack(side=LEFT, fill=X, expand=YES)

        # API Key
        key_frame = ttk.Frame(config_frame)
        key_frame.pack(fill=X, pady=5)
        ttk.Label(key_frame, text="API Key:", width=12).pack(side=LEFT)
        self.key_var = ttk.StringVar()
        self.key_entry = ttk.Entry(key_frame, textvariable=self.key_var, show="●", bootstyle="info")
        self.key_entry.pack(side=LEFT, fill=X, expand=YES, padx=(0, 10))
        self.show_key_var = ttk.BooleanVar()
        ttk.Checkbutton(key_frame, text="显示", variable=self.show_key_var, command=self.toggle_key_visibility, bootstyle="round-toggle").pack(side=LEFT)

        # === 操作按钮 ===
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=X, pady=(0, 10))

        ttk.Button(btn_frame, text="💰 查询余额", command=self.query_balance, bootstyle="primary", width=15).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="📋 查询日志", command=self.query_logs, bootstyle="info", width=15).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="📄 原始数据", command=self.show_raw_response, bootstyle="warning-outline", width=15).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="🧹 清空结果", command=self.clear_result, bootstyle="secondary-outline", width=15).pack(side=RIGHT, padx=5)

        # === 结果显示区 ===
        result_frame = ttk.Labelframe(parent, text=" 查询结果 ", padding=10, bootstyle="dark")
        result_frame.pack(fill=BOTH, expand=YES)

        self.result_notebook = ttk.Notebook(result_frame)
        self.result_notebook.pack(fill=BOTH, expand=YES)

        # 余额查询结果页
        balance_tab = ttk.Frame(self.result_notebook)
        self.result_notebook.add(balance_tab, text="💰 余额查询")
        self.result_text = ScrolledText(balance_tab, font=("Consolas", 10), wrap="word", autohide=True)
        self.result_text.pack(fill=BOTH, expand=YES)

        # 日志查询结果页
        logs_tab = ttk.Frame(self.result_notebook)
        self.result_notebook.add(logs_tab, text="📋 日志查询")

        log_columns = ("time", "model", "token", "input", "output", "quota")
        self.logs_tree = ttk.Treeview(logs_tab, columns=log_columns, show="headings", height=20, bootstyle="info")
        self.logs_tree.heading("time", text="时间")
        self.logs_tree.heading("model", text="模型")
        self.logs_tree.heading("token", text="Token名")
        self.logs_tree.heading("input", text="输入Token")
        self.logs_tree.heading("output", text="输出Token")
        self.logs_tree.heading("quota", text="消耗")

        self.logs_tree.column("time", width=120)
        self.logs_tree.column("model", width=180)
        self.logs_tree.column("token", width=100)
        self.logs_tree.column("input", width=90)
        self.logs_tree.column("output", width=90)
        self.logs_tree.column("quota", width=80)

        logs_scrollbar = ttk.Scrollbar(logs_tab, orient="vertical", command=self.logs_tree.yview)
        self.logs_tree.configure(yscrollcommand=logs_scrollbar.set)
        self.logs_tree.pack(side=LEFT, fill=BOTH, expand=YES)
        logs_scrollbar.pack(side=RIGHT, fill=Y)

    def toggle_key_visibility(self):
        """切换 API Key 显示/隐藏"""
        self.key_entry.configure(show="" if self.show_key_var.get() else "●")

    def create_background(self):
        """创建背景图片"""
        self.bg_original_image = None

        try:
            self.bg_original_image = Image.open(resource_path("assets/background.jpg"))
        except Exception as e:
            print(f"加载背景图片失败: {e}")
            self.bg_original_image = None

        self.bg_label = TkLabel(self.root)
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        self.bg_photo = None
        self.update_background()

        self.root.bind("<Configure>", self.on_window_resize)

    def update_background(self):
        """更新背景图片大小"""
        if self.bg_original_image is None:
            self.bg_label.configure(bg="#f0f4f8")
            return

        width = self.root.winfo_width()
        height = self.root.winfo_height()

        if width < 10 or height < 10:
            width, height = 950, 700

        try:
            bg_image = self.bg_original_image.resize((width, height), Image.Resampling.LANCZOS)
            overlay = Image.new('RGBA', bg_image.size, (255, 255, 255, 180))
            bg_image = bg_image.convert('RGBA')
            bg_image = Image.alpha_composite(bg_image, overlay)
            self.bg_photo = ImageTk.PhotoImage(bg_image)
            self.bg_label.configure(image=self.bg_photo)
        except Exception as e:
            print(f"更新背景失败: {e}")

    def on_window_resize(self, event):
        """窗口大小变化时更新背景"""
        if event.widget == self.root:
            if hasattr(self, '_resize_after_id'):
                self.root.after_cancel(self._resize_after_id)
            self._resize_after_id = self.root.after(100, self.update_background)

    def refresh_profile_list(self):
        """刷新站点列表（数据源：stats.json）"""
        for item in self.profile_tree.get_children():
            self.profile_tree.delete(item)

        self.stats_data = load_stats()
        sites = self.stats_data.get("sites", [])

        # 排序
        sort_key = getattr(self, '_sort_key', 'balance')
        sort_reverse = getattr(self, '_sort_reverse', True)

        if sort_key == "balance":
            sites_sorted = sorted(sites, key=lambda s: s.get("balance", 0), reverse=sort_reverse)
        else:
            sites_sorted = sorted(sites, key=lambda s: s.get("name", "").lower(), reverse=sort_reverse)

        for site in sites_sorted:
            name = site.get("name", "未命名")
            balance = site.get("balance", 0)
            unit = site.get("balance_unit", "USD")
            if unit == "USD":
                balance_display = f"${balance:.2f}"
            else:
                balance_display = f"{balance:,.0f} {unit}"
            self.profile_tree.insert("", "end", iid=site["id"], values=(name, balance_display))

        # 同步更新 stats_frame 的数据引用
        if hasattr(self, 'stats_frame'):
            self.stats_frame.stats_data = self.stats_data
            self.stats_frame.update_summary()

    def sort_profile_list(self, key):
        """切换排序方式"""
        if self._sort_key == key:
            # 同一列，切换升降序
            self._sort_reverse = not self._sort_reverse
        else:
            # 不同列，默认降序（余额）或升序（名称）
            self._sort_key = key
            self._sort_reverse = (key == "balance")

        # 更新表头显示
        if key == "balance":
            arrow = "↓" if self._sort_reverse else "↑"
            self.profile_tree.heading("balance", text=f"余额 {arrow}")
            self.profile_tree.heading("name", text="名称")
        else:
            arrow = "↓" if self._sort_reverse else "↑"
            self.profile_tree.heading("name", text=f"名称 {arrow}")
            self.profile_tree.heading("balance", text="余额")

        self.refresh_profile_list()

    def on_stats_save(self):
        """数据统计模块保存后的回调"""
        # 保存当前选中的站点 ID
        selection = self.profile_tree.selection()
        current_id = selection[0] if selection else None

        # 刷新列表
        self.refresh_profile_list()

        # 恢复选中状态
        if current_id:
            try:
                self.profile_tree.selection_set(current_id)
                # 更新 _current_site 引用
                site = get_site_by_id(self.stats_data, current_id)
                if site:
                    self._current_site = site
            except:
                pass

        self.status_var.set("✅ 站点信息已更新")

    def on_profile_select(self, event):
        """单击选择站点，同步到各模块"""
        selection = self.profile_tree.selection()
        if not selection:
            return

        site_id = selection[0]
        site = get_site_by_id(self.stats_data, site_id)
        if site:
            self._current_site = site
            self._sync_site_to_modules()
            self.status_var.set(f"✅ 已选择: {site.get('name', '')}")

    def _sync_site_to_modules(self):
        """同步当前选中的站点到各模块"""
        if not hasattr(self, '_current_site'):
            return

        site = self._current_site
        site_info = {
            "id": site.get("id", ""),
            "name": site.get("name", ""),
            "url": site.get("url", ""),
            "api_key": site.get("api_key", ""),
        }

        # 同步到余额查询模块
        self.name_var.set(site.get("name", ""))
        self.url_var.set(site.get("url", ""))
        self.key_var.set(site.get("api_key", ""))

        # 加载站点的高级设置
        self._current_profile_balance_auth_type = site.get("balance_auth_type", "bearer")
        self._current_profile_log_auth_type = site.get("log_auth_type", "url_key")
        self._current_profile_endpoints = site.get("endpoints", {})
        self._current_profile_proxy = site.get("proxy", "")

        # 同步到测试模块
        if hasattr(self, 'test_frame'):
            self.test_frame.set_current_site(site_info)

        # 同步到统计模块
        if hasattr(self, 'stats_frame'):
            self.stats_frame.set_current_site(site_info)

    def add_site_from_list(self):
        """添加新站点"""
        from konata_api.stats import create_site, add_site, SITE_TYPE_PAID

        site = create_site(name="新站点", url="https://", site_type=SITE_TYPE_PAID)
        add_site(self.stats_data, site)
        save_stats(self.stats_data)
        self.refresh_profile_list()

        # 选中新站点并同步
        self.profile_tree.selection_set(site["id"])
        self._current_site = site
        self._sync_site_to_modules()

        # 切换到数据统计标签页进行编辑
        self.main_notebook.select(0)
        self.status_var.set("✅ 已添加新站点，请在右侧编辑详情")

    def delete_site_from_list(self):
        """删除选中的站点"""
        from konata_api.stats import delete_site

        selection = self.profile_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择要删除的站点")
            return

        site_id = selection[0]
        site = get_site_by_id(self.stats_data, site_id)
        if not site:
            return

        if messagebox.askyesno("确认", f"确定删除站点「{site.get('name', '')}」吗？"):
            delete_site(self.stats_data, site_id)
            save_stats(self.stats_data)
            self.refresh_profile_list()

            # 同步刷新统计模块
            if hasattr(self, 'stats_frame'):
                self.stats_frame.stats_data = self.stats_data
                self.stats_frame.current_site_id = None
                self.stats_frame.clear_form()
                self.stats_frame.update_summary()

            self.status_var.set(f"🗑️ 已删除站点: {site.get('name', '')}")

    def open_all_checkin_from_list(self):
        """一键自动签到（有签到网址的才参与，有Cookie的调API，没有的打开浏览器）"""
        import webbrowser

        # 分类站点（必须有 checkin_url 才参与签到）
        api_sites = []  # 有 checkin_url + session_cookie 的站点，自动签到
        browser_sites = []  # 有 checkin_url 但没 cookie 的站点，打开浏览器

        for site in self.stats_data.get("sites", []):
            checkin_url = site.get("checkin_url", "").strip()
            if not checkin_url:
                continue  # 没有签到网址的不参与

            session_cookie = site.get("session_cookie", "").strip()
            url = site.get("url", "").strip()

            if session_cookie and url:
                api_sites.append(site)
            else:
                browser_sites.append(site)

        if not api_sites and not browser_sites:
            messagebox.showinfo("提示", "没有配置签到网址的站点\n\n请在「数据统计」中为站点配置签到网址")
            return

        # 构建确认信息
        msg_parts = []
        if api_sites:
            msg_parts.append(f"自动签到 {len(api_sites)} 个站点:\n" + "\n".join([f"  - {s.get('name', '未命名')}" for s in api_sites[:5]]) + ("\n  ..." if len(api_sites) > 5 else ""))
        if browser_sites:
            msg_parts.append(f"打开浏览器 {len(browser_sites)} 个站点:\n" + "\n".join([f"  - {s.get('name', '未命名')}" for s in browser_sites[:5]]) + ("\n  ..." if len(browser_sites) > 5 else ""))

        if not messagebox.askyesno("确认签到", "\n\n".join(msg_parts)):
            return

        # 打开浏览器签到
        for site in browser_sites:
            webbrowser.open(site.get("checkin_url", ""))

        # 自动 API 签到
        if api_sites:
            self.status_var.set("正在自动签到...")
            threading.Thread(target=self._do_batch_checkin, args=(api_sites,), daemon=True).start()

    def _do_batch_checkin(self, sites):
        """批量执行自动签到（后台线程）"""
        results = []
        total_quota = 0

        for site in sites:
            site_name = site.get("name", "未命名")
            site_id = site.get("id", "")
            base_url = site.get("url", "")
            session_cookie = site.get("session_cookie", "")
            user_id = site.get("checkin_user_id", "")

            result = do_checkin(base_url, session_cookie, user_id)

            if result.get("success"):
                quota = result.get("quota_awarded", 0)
                # quota 转换为 USD（500000 = $1）
                quota_usd = round(quota / 500000, 2) if quota else 0
                total_quota += quota_usd
                results.append(f"✅ {site_name}: +${quota_usd}")

                # 签到成功后，用 Cookie 查询真实余额并更新
                balance_result = query_balance_by_cookie(base_url, session_cookie, user_id)
                if balance_result.get("success"):
                    new_balance = balance_result.get("balance", 0)
                    update_site(self.stats_data, site_id, {"balance": new_balance, "balance_unit": "USD"})

                # 记录日志（记录 USD 值）
                add_checkin_log(site_name, site_id, True, quota_usd, result.get("message", ""))
            else:
                results.append(f"❌ {site_name}: {result.get('message', '失败')}")
                add_checkin_log(site_name, site_id, False, 0, result.get("message", ""))

        # 保存数据
        save_stats(self.stats_data)

        # 在主线程更新 UI
        self.root.after(0, lambda: self._show_checkin_results(results, total_quota))

    def _show_checkin_results(self, results, total_quota):
        """显示签到结果"""
        self.status_var.set(f"签到完成，共获得 ${total_quota:.2f}")

        # 刷新统计模块
        if hasattr(self, 'stats_frame'):
            self.stats_frame.stats_data = self.stats_data
            self.stats_frame.refresh_site_list()
            self.stats_frame.update_summary()

        # 显示结果弹窗
        result_text = "\n".join(results)
        summary = f"\n\n总计获得: ${total_quota:.2f}"
        messagebox.showinfo("签到结果", result_text + summary)

    def show_checkin_log(self):
        """显示签到记录"""
        logs = load_checkin_log()

        if not logs:
            messagebox.showinfo("签到记录", "暂无签到记录")
            return

        # 创建弹窗
        dialog = ttk.Toplevel(self.root)
        dialog.title("签到记录")
        dialog.geometry("600x400")
        dialog.transient(self.root)

        # 表格
        columns = ("time", "site", "status", "quota", "message")
        tree = ttk.Treeview(dialog, columns=columns, show="headings", bootstyle="info")
        tree.heading("time", text="时间")
        tree.heading("site", text="站点")
        tree.heading("status", text="状态")
        tree.heading("quota", text="获得额度")
        tree.heading("message", text="信息")

        tree.column("time", width=130)
        tree.column("site", width=100)
        tree.column("status", width=60)
        tree.column("quota", width=80)
        tree.column("message", width=200)

        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=LEFT, fill=BOTH, expand=YES, padx=(10, 0), pady=10)
        scrollbar.pack(side=RIGHT, fill=Y, padx=(0, 10), pady=10)

        # 填充数据（最近 100 条）
        for log in logs[:100]:
            status = "✅ 成功" if log.get("success") else "❌ 失败"
            quota = log.get("quota_awarded", 0)
            tree.insert("", "end", values=(
                log.get("time", ""),
                log.get("site_name", ""),
                status,
                f"+{quota}" if quota > 0 else "-",
                log.get("message", "")
            ))

    def open_profile_advanced(self):
        """打开站点高级设置对话框"""
        if not hasattr(self, '_current_site') or not self._current_site:
            messagebox.showwarning("提示", "请先选择一个站点")
            return

        site = self._current_site

        # 构造 profile 格式数据给 ProfileAdvancedDialog
        profile = {
            "name": site.get("name", ""),
            "url": site.get("url", ""),
            "key": site.get("api_key", ""),
            "balance_auth_type": site.get("balance_auth_type", "bearer"),
            "log_auth_type": site.get("log_auth_type", "url_key"),
            "proxy": site.get("proxy", ""),
            "endpoints": site.get("endpoints", {})
        }

        def on_save(updated_profile):
            # 更新 stats.json 中的站点数据
            site["balance_auth_type"] = updated_profile.get("balance_auth_type", "bearer")
            site["log_auth_type"] = updated_profile.get("log_auth_type", "url_key")
            site["proxy"] = updated_profile.get("proxy", "")
            site["endpoints"] = updated_profile.get("endpoints", {})

            save_stats(self.stats_data)
            self.status_var.set(f"✅ 站点 '{site.get('name', '')}' 高级设置已保存")

            # 更新内存中的配置
            self._current_profile_balance_auth_type = site.get("balance_auth_type", "bearer")
            self._current_profile_log_auth_type = site.get("log_auth_type", "url_key")
            self._current_profile_endpoints = site.get("endpoints", {})
            self._current_profile_proxy = site.get("proxy", "")

        ProfileAdvancedDialog(self.root, profile.copy(), on_save)

    def query_balance(self):
        """查询当前配置的余额"""
        url = self.url_var.get().strip()
        key = self.key_var.get().strip()

        if not url or not key:
            messagebox.showwarning("提示", "请填写 Base URL 和 API Key")
            return

        # 获取 profile 级别的配置，如果没有则使用全局配置
        profile_endpoints = getattr(self, '_current_profile_endpoints', {})
        global_endpoints = self.config.get("api_endpoints", {})

        sub_api = profile_endpoints.get("balance_subscription") or global_endpoints.get("balance_subscription", "/v1/dashboard/billing/subscription")
        usage_api = profile_endpoints.get("balance_usage") or global_endpoints.get("balance_usage", "/v1/dashboard/billing/usage")
        auth_type = getattr(self, '_current_profile_balance_auth_type', 'bearer')

        self.status_var.set("⏳ 正在查询余额...")
        self.root.update()

        def query_thread():
            try:
                result = query_balance(key, url, subscription_api=sub_api, usage_api=usage_api, auth_type=auth_type)
                self.root.after(0, lambda: self.on_balance_result(result, self.name_var.get() or url))
            except Exception as e:
                self.root.after(0, lambda: self.on_query_error(str(e)))

        threading.Thread(target=query_thread, daemon=True).start()

    def on_balance_result(self, result, name):
        """处理余额查询结果"""
        raw_data = result.get("raw_response", result)
        self.last_raw_response["balance"] = raw_data
        self.save_raw_response_to_file()
        self.display_balance_result(name, result)
        self.save_result(name, "balance", result)
        self.status_var.set("✅ 余额查询完成")

    def on_query_error(self, error_msg):
        """处理查询错误"""
        self.result_text.insert("end", f"❌ 查询出错: {error_msg}\n")
        self.status_var.set("❌ 查询出错")

    def query_all_balance(self):
        """查询所有配置的余额"""
        sites = self.stats_data.get("sites", [])
        if not sites:
            messagebox.showwarning("提示", "没有保存的站点配置")
            return

        self.result_text.delete("1.0", "end")
        self.result_text.insert("end", f"{'═'*50}\n")
        self.result_text.insert("end", f"  📊 批量查询 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.result_text.insert("end", f"{'═'*50}\n\n")

        global_endpoints = self.config.get("api_endpoints", {})

        # 汇总数据
        summary_data = {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "sites": []
        }

        for i, site in enumerate(sites):
            name = site.get("name", f"站点{i+1}")
            url = site.get("url", "")
            key = site.get("api_key", "")

            if not url or not key:
                self.result_text.insert("end", f"⚠️ 【{name}】配置不完整，跳过\n\n")
                summary_data["skipped"] += 1
                summary_data["sites"].append({
                    "name": name,
                    "balance": 0,
                    "unit": "",
                    "today_cost": 0,
                    "error": "配置不完整"
                })
                continue

            self.status_var.set(f"⏳ 正在查询: {name} ({i+1}/{len(sites)})")
            self.root.update()

            # 使用全局接口配置
            sub_api = global_endpoints.get("balance_subscription", "/v1/dashboard/billing/subscription")
            usage_api = global_endpoints.get("balance_usage", "/v1/dashboard/billing/usage")
            auth_type = "bearer"

            try:
                result = query_balance(key, url, subscription_api=sub_api, usage_api=usage_api, auth_type=auth_type)
                self.display_balance_result(name, result, show_header=False)

                # 收集站点数据
                site_data = self.extract_site_summary(name, result)
                summary_data["sites"].append(site_data)

                if site_data.get("error"):
                    summary_data["failed"] += 1
                else:
                    summary_data["success"] += 1

            except Exception as e:
                self.result_text.insert("end", f"❌ 【{name}】查询出错: {e}\n\n")
                summary_data["failed"] += 1
                summary_data["sites"].append({
                    "name": name,
                    "balance": 0,
                    "unit": "",
                    "today_cost": 0,
                    "error": str(e)
                })

        self.status_var.set(f"✅ 批量查询完成，共 {len(sites)} 个站点")

        # 弹出汇总对话框
        threshold = self.config.get("low_balance_threshold", 10)
        BalanceSummaryDialog(self.root, summary_data, low_balance_threshold=threshold)

    def query_all_balance_by_cookie_and_save(self):
        """使用 Cookie 查询所有站点余额并保存到 stats.json"""
        sites = self.stats_data.get("sites", [])
        # 筛选有 session_cookie 的站点
        cookie_sites = [s for s in sites if s.get("session_cookie", "").strip()]

        if not cookie_sites:
            messagebox.showwarning("提示", "没有配置 Session Cookie 的站点\n\n请在「数据统计」中为站点配置 Cookie")
            return

        if not messagebox.askyesno("确认", f"将查询 {len(cookie_sites)} 个站点的余额并保存\n\n继续吗？"):
            return

        self.status_var.set("正在查询余额...")
        threading.Thread(target=self._do_batch_balance_query, args=(cookie_sites,), daemon=True).start()

    def _do_batch_balance_query(self, sites):
        """批量查询余额（后台线程）"""
        results = []
        success_count = 0
        fail_count = 0

        for site in sites:
            site_name = site.get("name", "未命名")
            site_id = site.get("id", "")
            base_url = site.get("url", "")
            session_cookie = site.get("session_cookie", "")
            user_id = site.get("checkin_user_id", "")

            self.root.after(0, lambda n=site_name: self.status_var.set(f"正在查询: {n}"))

            result = query_balance_by_cookie(base_url, session_cookie, user_id)

            if result.get("success"):
                new_balance = result.get("balance", 0)
                update_site(self.stats_data, site_id, {"balance": new_balance, "balance_unit": "USD"})
                results.append(f"✅ {site_name}: ${new_balance:.2f}")
                success_count += 1
            else:
                results.append(f"❌ {site_name}: {result.get('message', '查询失败')}")
                fail_count += 1

        # 保存数据
        save_stats(self.stats_data)

        # 在主线程更新 UI
        self.root.after(0, lambda: self._show_balance_query_results(results, success_count, fail_count))

    def _show_balance_query_results(self, results, success_count, fail_count):
        """显示余额查询结果"""
        self.status_var.set(f"查询完成: {success_count} 成功, {fail_count} 失败")

        # 刷新列表
        self.refresh_profile_list()

        # 刷新统计模块
        if hasattr(self, 'stats_frame'):
            self.stats_frame.stats_data = self.stats_data
            self.stats_frame.refresh_site_list()
            self.stats_frame.update_summary()

        # 显示结果弹窗
        result_text = "\n".join(results)
        messagebox.showinfo("余额查询结果", result_text)

    def extract_site_summary(self, name, result):
        """从查询结果中提取站点汇总数据"""
        site_data = {
            "name": name,
            "balance": 0,
            "unit": "USD",
            "today_cost": 0,
            "error": None
        }

        if "error" in result:
            site_data["error"] = result["error"]
            return site_data

        # OpenAI 兼容格式 (hard_limit_usd)
        if "hard_limit_usd" in result:
            site_data["balance"] = result.get('remaining_usd', 0)
            site_data["unit"] = "USD"

        # NewAPI Token 格式
        elif "total_granted" in result:
            site_data["balance"] = result.get('total_available', 0)
            site_data["unit"] = "Token"

        # sub2api / 新 API 体系格式 (balance)
        elif "balance" in result:
            site_data["balance"] = result.get('balance', 0)
            site_data["unit"] = result.get('unit', 'USD') or 'USD'

        # 今日消耗
        site_data["today_cost"] = result.get('today_cost', 0)

        return site_data

    def display_balance_result(self, name, result, show_header=True):
        """显示余额结果"""
        self.result_notebook.select(0)

        if show_header:
            self.result_text.insert("end", f"\n{'═'*50}\n")
            self.result_text.insert("end", f"  查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.result_text.insert("end", f"{'═'*50}\n\n")

        self.result_text.insert("end", f"📌 【{name}】\n")

        if "error" in result:
            self.result_text.insert("end", f"   ❌ 错误: {result['error']}\n\n")
            self.result_text.see("end")
            return

        has_data = False

        # OpenAI 兼容格式 (hard_limit_usd)
        if "hard_limit_usd" in result:
            remaining = result.get('remaining_usd', 0)
            total = result.get('hard_limit_usd', 0)
            used = result.get('used_usd', 0)
            pct = (remaining / total * 100) if total > 0 else 0
            self.result_text.insert("end", f"   💵 USD: ${remaining:.2f} / ${total:.2f} ({pct:.1f}%)\n")
            has_data = True

        # NewAPI Token 格式
        if "total_granted" in result:
            available = result.get('total_available', 0)
            granted = result.get('total_granted', 0)
            pct = (available / granted * 100) if granted > 0 else 0
            self.result_text.insert("end", f"   🎫 Token: {available:,} / {granted:,} ({pct:.1f}%)\n")
            has_data = True

        # sub2api / 新 API 体系格式 (balance)
        if "balance" in result and "hard_limit_usd" not in result:
            balance = result.get('balance', 0)
            unit = result.get('unit', 'USD')
            plan_name = result.get('plan_name', '')
            if plan_name:
                self.result_text.insert("end", f"   📋 套餐: {plan_name}\n")
            self.result_text.insert("end", f"   💰 余额: {balance:.2f} {unit}\n")
            has_data = True

        # 用量统计 (sub2api /v1/usage 或 /api/v1/usage/dashboard/stats)
        if "total_cost" in result or "today_cost" in result:
            total_cost = result.get('total_cost', 0)
            today_cost = result.get('today_cost', 0)
            total_requests = result.get('total_requests', 0)
            today_requests = result.get('today_requests', 0)
            total_tokens = result.get('total_tokens', 0)
            today_tokens = result.get('today_tokens', 0)

            # 格式化大数字
            def fmt_num(n):
                if n >= 1_000_000_000:
                    return f"{n/1_000_000_000:.1f}B"
                elif n >= 1_000_000:
                    return f"{n/1_000_000:.1f}M"
                elif n >= 1_000:
                    return f"{n/1_000:.1f}K"
                return str(int(n))

            self.result_text.insert("end", f"   📊 消耗: ${total_cost:.2f} (今日: ${today_cost:.2f})\n")
            self.result_text.insert("end", f"   📈 请求: {fmt_num(total_requests)} (今日: {fmt_num(today_requests)})\n")
            self.result_text.insert("end", f"   🔢 Token: {fmt_num(total_tokens)} (今日: {fmt_num(today_tokens)})\n")
            has_data = True

        if not has_data:
            self.result_text.insert("end", f"   ⚠️ 未获取到数据\n")

        self.result_text.insert("end", "\n")
        self.result_text.see("end")

    def query_logs(self):
        """查询日志"""
        url = self.url_var.get().strip()
        key = self.key_var.get().strip()

        if not url or not key:
            messagebox.showwarning("提示", "查询日志需要填写 Base URL 和 API Key")
            return

        # 获取 profile 级别的配置，如果没有则使用全局配置
        profile_endpoints = getattr(self, '_current_profile_endpoints', {})
        global_endpoints = self.config.get("api_endpoints", {})

        logs_api = profile_endpoints.get("logs") or global_endpoints.get("logs", "/api/log/token")
        page_size = global_endpoints.get("logs_page_size", 50)
        proxy_url = getattr(self, '_current_profile_proxy', '')
        auth_type = getattr(self, '_current_profile_log_auth_type', 'url_key')

        self.status_var.set("⏳ 正在查询日志...")
        self.root.update()

        def query_thread():
            try:
                result = query_logs(key, url, page_size=page_size, page=1, order="desc", custom_api_path=logs_api, proxy_url=proxy_url, auth_type=auth_type)
                self.root.after(0, lambda: self.on_logs_result(result, self.name_var.get() or "未命名"))
            except Exception as e:
                self.root.after(0, lambda: self.on_logs_error(str(e)))

        threading.Thread(target=query_thread, daemon=True).start()

    def on_logs_result(self, result, name):
        """处理日志查询结果"""
        raw_data = result.get("raw_response", result)
        self.last_raw_response["logs"] = raw_data
        self.save_raw_response_to_file()
        self.display_logs_result(result)
        self.save_result(name, "logs", result)
        self.status_var.set("✅ 日志查询完成")

    def on_logs_error(self, error_msg):
        """处理日志查询错误"""
        self.result_notebook.select(1)
        for item in self.logs_tree.get_children():
            self.logs_tree.delete(item)
        self.logs_tree.insert("", "end", values=("错误", error_msg, "", "", "", ""))
        self.status_var.set("❌ 查询出错")

    def save_raw_response_to_file(self):
        """保存原始返回数据到文件"""
        try:
            # 确保 config 目录存在
            config_dir = os.path.dirname(self.raw_response_file)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)

            data_to_save = {
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "balance": self.last_raw_response.get("balance"),
                "logs": self.last_raw_response.get("logs")
            }
            with open(self.raw_response_file, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存原始数据到文件失败: {e}")

    def load_raw_response_from_file(self):
        """从文件加载原始返回数据"""
        try:
            if os.path.exists(self.raw_response_file):
                with open(self.raw_response_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"读取原始数据文件失败: {e}")
        return None

    def display_logs_result(self, result):
        """显示日志结果"""
        self.result_notebook.select(1)

        for item in self.logs_tree.get_children():
            self.logs_tree.delete(item)

        if "error" in result:
            self.logs_tree.insert("", "end", values=("错误", result['error'], "", "", "", ""))
            return

        total = result.get("total", 0)
        items = result.get("items", [])

        if not items:
            self.logs_tree.insert("", "end", values=("无数据", "没有查询到日志记录", "", "", "", ""))
            return

        for item in items:
            created_at = item.get("created_at", 0)
            time_str = datetime.fromtimestamp(created_at).strftime("%m-%d %H:%M:%S") if created_at else "未知"

            model_name = item.get("model_name", "未知")
            token_name = item.get("token_name", "-")
            prompt_tokens = item.get("prompt_tokens", 0)
            completion_tokens = item.get("completion_tokens", 0)
            quota = item.get("quota", 0)

            self.logs_tree.insert("", "end", values=(
                time_str,
                model_name,
                token_name,
                f"{prompt_tokens:,}",
                f"{completion_tokens:,}",
                f"{quota:,}"
            ))

        self.status_var.set(f"✅ 共查询到 {total} 条日志记录")

    def clear_result(self):
        """清空结果"""
        self.result_text.delete("1.0", "end")
        for item in self.logs_tree.get_children():
            self.logs_tree.delete(item)
        self.status_var.set("🧹 已清空")

    def show_raw_response(self):
        """显示原始返回数据弹窗"""
        current_tab = self.result_notebook.index(self.result_notebook.select())

        data = None
        if current_tab == 0:
            data = self.last_raw_response.get("balance")
            if data is None:
                file_data = self.load_raw_response_from_file()
                if file_data:
                    data = file_data.get("balance")
            title = "余额查询 - 原始返回数据"
        else:
            data = self.last_raw_response.get("logs")
            if data is None:
                file_data = self.load_raw_response_from_file()
                if file_data:
                    data = file_data.get("logs")
            title = "日志查询 - 原始返回数据"

        if data is None:
            messagebox.showinfo("提示", "还没有查询过数据，请先执行查询")
            return

        RawResponseDialog(self.root, title, data)

    def save_result(self, profile_name: str, result_type: str, result: dict):
        """保存查询结果到文件"""
        results_dir = os.path.join(get_exe_dir(), "results")
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)

        safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in profile_name)
        filename = os.path.join(results_dir, f"{safe_name}_{result_type}.json")

        result_with_time = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "profile_name": profile_name,
            "result": result
        }

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(result_with_time, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存结果失败: {e}")

    def open_settings(self):
        """打开设置对话框"""
        SettingsDialog(self.root, self.config, app=self)

    def open_stats(self):
        """切换到统计标签页"""
        self.main_notebook.select(0)
        # 更新 profiles 数据
        self.stats_frame.set_profiles(self.config.get("profiles", []))

    def open_test(self):
        """切换到测试标签页"""
        self.main_notebook.select(2)

    def show_window(self):
        """显示主窗口"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide_window(self):
        """隐藏主窗口到托盘"""
        self.root.withdraw()

    def on_close_window(self):
        """窗口关闭按钮处理"""
        if self.config.get("minimize_to_tray", True):
            self.hide_window()
        else:
            self.quit_app()

    def quit_app(self):
        """真正退出程序"""
        self.stop_auto_query()
        if hasattr(self, 'tray'):
            self.tray.stop()
        self.root.destroy()

    # === 自动查询功能 ===

    def start_auto_query(self):
        """启动自动查询定时器"""
        auto_query = self.config.get("auto_query", {})
        if not auto_query.get("enabled", False):
            return

        interval_minutes = auto_query.get("interval_minutes", 30)
        interval_ms = interval_minutes * 60 * 1000  # 转换为毫秒

        self._auto_query_timer_id = self.root.after(interval_ms, self._auto_query_tick)
        self.status_var.set(f"⏰ 自动查询已启用，每 {interval_minutes} 分钟查询一次")

    def stop_auto_query(self):
        """停止自动查询定时器"""
        if self._auto_query_timer_id:
            self.root.after_cancel(self._auto_query_timer_id)
            self._auto_query_timer_id = None

    def _auto_query_tick(self):
        """自动查询定时器回调"""
        # 执行批量查询
        self.query_all_balance()

        # 重新设置下一次定时
        auto_query = self.config.get("auto_query", {})
        if auto_query.get("enabled", False):
            interval_minutes = auto_query.get("interval_minutes", 30)
            interval_ms = interval_minutes * 60 * 1000
            self._auto_query_timer_id = self.root.after(interval_ms, self._auto_query_tick)

    def update_auto_query(self):
        """更新自动查询设置（从设置对话框调用）"""
        self.stop_auto_query()
        self.start_auto_query()


def main():
    root = ttk.Window(themename="cosmo")
    app = ApiQueryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
