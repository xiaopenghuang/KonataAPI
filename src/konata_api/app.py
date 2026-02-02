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

from konata_api.api import query_balance, query_logs
from konata_api.utils import (
    get_exe_dir, resource_path, load_config, save_config
)
from konata_api.dialogs import SettingsDialog, RawResponseDialog
from konata_api.tray import TrayIcon


class ApiQueryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("此方API查查")
        self.root.geometry("950x700")
        self.root.minsize(850, 650)

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

        # === 左侧：配置列表 ===
        left_frame = ttk.Labelframe(main_frame, text=" 中转站列表 ", padding=15, bootstyle="info")
        left_frame.pack(side=LEFT, fill=Y, padx=(0, 15))

        # 配置列表 Treeview
        columns = ("name", "url")
        self.profile_tree = ttk.Treeview(left_frame, columns=columns, show="headings", height=18, bootstyle="info")
        self.profile_tree.heading("name", text="名称")
        self.profile_tree.heading("url", text="地址")
        self.profile_tree.column("name", width=90)
        self.profile_tree.column("url", width=170)
        self.profile_tree.pack(fill=BOTH, expand=YES)
        self.profile_tree.bind("<<TreeviewSelect>>", self.on_profile_select)
        self.profile_tree.bind("<Double-1>", self.on_profile_double_click)

        # 列表操作按钮
        list_btn_frame = ttk.Frame(left_frame)
        list_btn_frame.pack(fill=X, pady=(15, 0))
        ttk.Button(list_btn_frame, text="🔄 查询全部余额", command=self.query_all_balance, bootstyle="success-outline", width=20).pack(fill=X, pady=3)
        ttk.Button(list_btn_frame, text="🗑️ 删除选中", command=self.delete_profile, bootstyle="danger-outline", width=20).pack(fill=X, pady=3)

        # === 右侧：详情和结果 ===
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=LEFT, fill=BOTH, expand=YES)

        # === 标题 ===
        title_frame = ttk.Frame(right_frame)
        title_frame.pack(fill=X, pady=(0, 15))

        title_left = ttk.Frame(title_frame)
        title_left.pack(side=LEFT, fill=X, expand=YES)
        ttk.Label(title_left, text="此方API查查", font=("Microsoft YaHei", 16, "bold"), bootstyle="inverse-primary").pack(anchor=W)
        ttk.Label(title_left, text="支持多中转站配置管理与批量查询", font=("Microsoft YaHei", 9), bootstyle="secondary").pack(anchor=W)

        ttk.Button(title_frame, text="⚙️ 设置", command=self.open_settings, bootstyle="secondary-outline", width=10).pack(side=RIGHT, padx=5)

        # === 配置详情区 ===
        config_frame = ttk.Labelframe(right_frame, text=" 配置详情 ", padding=15, bootstyle="primary")
        config_frame.pack(fill=X, pady=(0, 15))

        # 配置名称
        name_frame = ttk.Frame(config_frame)
        name_frame.pack(fill=X, pady=5)
        ttk.Label(name_frame, text="配置名称:", width=12).pack(side=LEFT)
        self.name_var = ttk.StringVar()
        ttk.Entry(name_frame, textvariable=self.name_var, width=25, bootstyle="info").pack(side=LEFT, padx=(0, 10))
        ttk.Button(name_frame, text="💾 保存配置", command=self.save_profile, bootstyle="success", width=12).pack(side=RIGHT)

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

        # 日志代理（按站点配置）
        proxy_frame = ttk.Frame(config_frame)
        proxy_frame.pack(fill=X, pady=5)
        ttk.Label(proxy_frame, text="日志代理:", width=12).pack(side=LEFT)
        self.proxy_var = ttk.StringVar()
        ttk.Entry(proxy_frame, textvariable=self.proxy_var, bootstyle="info").pack(side=LEFT, fill=X, expand=YES)
        ttk.Label(proxy_frame, text="(可选)", bootstyle="secondary").pack(side=LEFT, padx=(5, 0))

        # === 操作按钮 ===
        btn_frame = ttk.Frame(right_frame)
        btn_frame.pack(fill=X, pady=(0, 15))

        ttk.Button(btn_frame, text="💰 查询余额", command=self.query_balance, bootstyle="primary", width=15).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="📋 查询日志", command=self.query_logs, bootstyle="info", width=15).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="📄 原始数据", command=self.show_raw_response, bootstyle="warning-outline", width=15).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="🧹 清空结果", command=self.clear_result, bootstyle="secondary-outline", width=15).pack(side=RIGHT, padx=5)

        # === 结果显示区 ===
        result_frame = ttk.Labelframe(right_frame, text=" 查询结果 ", padding=10, bootstyle="dark")
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

        # === 状态栏 ===
        self.status_var = ttk.StringVar(value="就绪 - 双击左侧列表选择配置，或手动输入新配置")
        status_bar = ttk.Label(right_frame, textvariable=self.status_var, bootstyle="inverse-secondary", padding=(10, 5))
        status_bar.pack(fill=X, pady=(15, 0))

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
        """刷新配置列表"""
        for item in self.profile_tree.get_children():
            self.profile_tree.delete(item)

        for p in self.config.get("profiles", []):
            name = p.get("name", "未命名")
            url = p.get("url", "")
            url_display = url.replace("https://", "").replace("http://", "")[:25]
            if len(url) > 30:
                url_display += "..."
            self.profile_tree.insert("", "end", values=(name, url_display))

    def on_profile_select(self, event):
        """单击选择配置"""
        pass

    def on_profile_double_click(self, event):
        """双击加载配置"""
        selection = self.profile_tree.selection()
        if selection:
            idx = self.profile_tree.index(selection[0])
            self.load_profile(idx)
            self.status_var.set(f"✅ 已加载配置: {self.name_var.get()}")

    def load_profile(self, idx):
        """加载指定配置"""
        profiles = self.config.get("profiles", [])
        if idx < len(profiles):
            p = profiles[idx]
            self.name_var.set(p.get("name", ""))
            self.url_var.set(p.get("url", ""))
            self.key_var.set(p.get("key", ""))
            self.proxy_var.set(p.get("proxy", ""))

    def save_profile(self):
        """保存当前配置"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "请输入配置名称")
            return

        profile = {
            "name": name,
            "url": self.url_var.get().strip(),
            "key": self.key_var.get().strip(),
            "proxy": self.proxy_var.get().strip(),
        }

        profiles = self.config.get("profiles", [])
        found = False
        for i, p in enumerate(profiles):
            if p.get("name") == name:
                profiles[i] = profile
                found = True
                break

        if not found:
            profiles.append(profile)

        self.config["profiles"] = profiles
        save_config(self.config)
        self.refresh_profile_list()
        self.status_var.set(f"✅ 配置 '{name}' 已保存")

    def delete_profile(self):
        """删除选中配置"""
        selection = self.profile_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择要删除的配置")
            return

        idx = self.profile_tree.index(selection[0])
        profiles = self.config.get("profiles", [])
        if idx < len(profiles):
            name = profiles[idx].get("name", "")
            if messagebox.askyesno("确认", f"确定删除配置 '{name}' 吗？"):
                del profiles[idx]
                self.config["profiles"] = profiles
                save_config(self.config)
                self.refresh_profile_list()
                self.status_var.set(f"🗑️ 配置 '{name}' 已删除")

    def query_balance(self):
        """查询当前配置的余额"""
        url = self.url_var.get().strip()
        key = self.key_var.get().strip()

        if not url or not key:
            messagebox.showwarning("提示", "请填写 Base URL 和 API Key")
            return

        endpoints = self.config.get("api_endpoints", {})
        sub_api = endpoints.get("balance_subscription", "/v1/dashboard/billing/subscription")
        usage_api = endpoints.get("balance_usage", "/v1/dashboard/billing/usage")

        self.status_var.set("⏳ 正在查询余额...")
        self.root.update()

        def query_thread():
            try:
                result = query_balance(key, url, subscription_api=sub_api, usage_api=usage_api)
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
        profiles = self.config.get("profiles", [])
        if not profiles:
            messagebox.showwarning("提示", "没有保存的配置")
            return

        self.result_text.delete("1.0", "end")
        self.result_text.insert("end", f"{'═'*50}\n")
        self.result_text.insert("end", f"  📊 批量查询 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.result_text.insert("end", f"{'═'*50}\n\n")

        for i, p in enumerate(profiles):
            name = p.get("name", f"配置{i+1}")
            url = p.get("url", "")
            key = p.get("key", "")

            if not url or not key:
                self.result_text.insert("end", f"⚠️ 【{name}】配置不完整，跳过\n\n")
                continue

            self.status_var.set(f"⏳ 正在查询: {name} ({i+1}/{len(profiles)})")
            self.root.update()

            try:
                result = query_balance(key, url)
                self.display_balance_result(name, result, show_header=False)
            except Exception as e:
                self.result_text.insert("end", f"❌ 【{name}】查询出错: {e}\n\n")

        self.status_var.set(f"✅ 批量查询完成，共 {len(profiles)} 个配置")

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

        if "hard_limit_usd" in result:
            remaining = result.get('remaining_usd', 0)
            total = result.get('hard_limit_usd', 0)
            used = result.get('used_usd', 0)
            pct = (remaining / total * 100) if total > 0 else 0
            self.result_text.insert("end", f"   💵 USD: ${remaining:.2f} / ${total:.2f} ({pct:.1f}%)\n")

        if "total_granted" in result:
            available = result.get('total_available', 0)
            granted = result.get('total_granted', 0)
            pct = (available / granted * 100) if granted > 0 else 0
            self.result_text.insert("end", f"   🎫 Token: {available:,} / {granted:,} ({pct:.1f}%)\n")

        self.result_text.insert("end", "\n")
        self.result_text.see("end")

    def query_logs(self):
        """查询日志"""
        url = self.url_var.get().strip()
        key = self.key_var.get().strip()

        if not url or not key:
            messagebox.showwarning("提示", "查询日志需要填写 Base URL 和 API Key")
            return

        endpoints = self.config.get("api_endpoints", {})
        logs_api = endpoints.get("logs", "/api/log/token")
        page_size = endpoints.get("logs_page_size", 50)
        proxy_url = self.proxy_var.get().strip()

        self.status_var.set("⏳ 正在查询日志...")
        self.root.update()

        def query_thread():
            try:
                result = query_logs(key, url, page_size=page_size, page=1, order="desc", custom_api_path=logs_api, proxy_url=proxy_url)
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
