"""
统计模块 GUI - 站点档案管理
"""
import io
import json
from datetime import datetime
import webbrowser
import ttkbootstrap as ttk
import tkinter as tk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledFrame, ScrolledText
from tkinter import messagebox, Text
from PIL import Image, ImageTk

from konata_api.utils import resource_path
from konata_api.stats import (
    load_stats, save_stats, create_site, add_site, update_site, delete_site,
    get_site_by_id, add_recharge_record, delete_recharge_record,
    add_checkin_log,
    import_from_profiles, get_stats_summary,
    create_balance_bar_chart, create_type_stats_chart,
    create_recharge_trend_chart, create_checkin_activity_chart,
    SITE_TYPE_PAID, SITE_TYPE_FREE, SITE_TYPE_SUBSCRIPTION, SITE_TYPE_LABELS
)
from konata_api.api import query_balance_by_cookie, do_checkin


def fit_toplevel(window, preferred_width, preferred_height, min_width=520, min_height=360):
    """根据屏幕尺寸自适应弹窗大小并居中"""
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()

    width = min(preferred_width, max(screen_w - 60, min_width))
    height = min(preferred_height, max(screen_h - 120, min_height))
    width = max(width, min_width)
    height = max(height, min_height)

    x = max((screen_w - width) // 2, 0)
    y = max((screen_h - height) // 2, 0)
    window.geometry(f"{width}x{height}+{x}+{y}")


class StatsFrame(ttk.Frame):
    """统计模块面板（嵌入式 Frame）"""

    def __init__(self, parent, profiles=None, show_site_list=True, on_save_callback=None, **kwargs):
        """
        Args:
            parent: 父窗口
            profiles: 主配置中的 profiles 列表（用于导入）
            show_site_list: 是否显示站点列表（嵌入主窗口时可隐藏）
            on_save_callback: 保存站点后的回调函数
        """
        super().__init__(parent, **kwargs)
        self.profiles = profiles or []
        self.show_site_list = show_site_list
        self.on_save_callback = on_save_callback
        self.stats_data = load_stats()
        self.current_site_id = None
        self.charts_loaded = False  # 图表是否已加载

        self.create_widgets()
        if self.show_site_list:
            self.refresh_site_list()
        self.update_summary()

    def set_profiles(self, profiles):
        """更新 profiles 列表"""
        self.profiles = profiles or []

    def set_current_site(self, site_info: dict):
        """设置当前站点（从外部调用）"""
        site_id = site_info.get("id", "")
        url = site_info.get("url", "").rstrip("/")
        name = site_info.get("name", "")
        api_key = site_info.get("api_key", "")

        # 优先按 ID 查找
        if site_id:
            site = get_site_by_id(self.stats_data, site_id)
            if site:
                self.current_site_id = site["id"]
                self.load_site_to_form(site)
                return

        # 如果没有 ID，按 URL 查找（兼容旧逻辑）
        for site in self.stats_data.get("sites", []):
            if site.get("url", "").rstrip("/") == url:
                self.current_site_id = site["id"]
                self.load_site_to_form(site)
                return

        # 如果不存在，自动创建新站点
        new_site = create_site(name=name, url=url, site_type=SITE_TYPE_PAID)
        new_site["api_key"] = api_key
        add_site(self.stats_data, new_site)
        save_stats(self.stats_data)

        self.current_site_id = new_site["id"]
        self.load_site_to_form(new_site)

        # 刷新站点列表（如果有的话）
        if self.show_site_list:
            self.refresh_site_list()
        self.update_summary()

    def create_widgets(self):
        """创建主界面"""
        # 使用 ScrolledFrame 包裹整个内容
        self.scroll_frame = ScrolledFrame(self, autohide=True)
        self.scroll_frame.pack(fill=BOTH, expand=YES)

        main_frame = ttk.Frame(self.scroll_frame, padding=10)
        main_frame.pack(fill=BOTH, expand=YES)

        if self.show_site_list:
            # 上半部分：站点管理（左右平均分）
            top_frame = ttk.Frame(main_frame)
            top_frame.pack(fill=BOTH, expand=YES, pady=(0, 10))

            # 配置左右各占一半
            top_frame.columnconfigure(0, weight=1)
            top_frame.columnconfigure(1, weight=1)
            top_frame.rowconfigure(0, weight=1)

            # 左侧：站点列表
            left_frame = ttk.Labelframe(top_frame, text=" 站点列表 ", padding=10)
            left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

            self.create_site_list(left_frame)

            # 右侧：站点详情/编辑
            right_frame = ttk.Labelframe(top_frame, text=" 站点详情 ", padding=10)
            right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

            self.create_site_form(right_frame)
        else:
            # 单栏模式：只显示站点详情（站点由全局列表控制）
            detail_frame = ttk.Labelframe(main_frame, text=" 站点详情 ", padding=10)
            detail_frame.pack(fill=BOTH, expand=YES, pady=(0, 10))

            self.create_site_form(detail_frame)

        # 下半部分：图表区域
        bottom_frame = ttk.Labelframe(main_frame, text=" 统计图表 ", padding=10)
        bottom_frame.pack(fill=X, pady=(0, 0))

        self.create_charts_area(bottom_frame)

    def create_site_list(self, parent):
        """创建站点列表"""
        # 列表框
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=BOTH, expand=YES)

        columns = ("name", "type", "balance")
        self.site_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15, bootstyle="info")
        self.site_tree.heading("name", text="站点名称")
        self.site_tree.heading("type", text="类型")
        self.site_tree.heading("balance", text="余额")

        self.site_tree.column("name", width=150)
        self.site_tree.column("type", width=80)
        self.site_tree.column("balance", width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.site_tree.yview)
        self.site_tree.configure(yscrollcommand=scrollbar.set)
        self.site_tree.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.site_tree.bind("<<TreeviewSelect>>", self.on_site_select)

        # 按钮区
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=X, pady=(10, 0))

        ttk.Button(btn_frame, text="从配置导入", command=self.import_from_config, bootstyle="info", width=10).pack(side=LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="🌐 打开网址", command=self.open_site_url, bootstyle="primary-outline", width=10).pack(side=LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="添加", command=self.add_new_site, bootstyle="success", width=6).pack(side=LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="删除", command=self.delete_current_site, bootstyle="danger", width=6).pack(side=LEFT)

    def create_site_form(self, parent):
        """创建站点编辑表单"""
        # 使用 notebook 分两个 tab：基本信息 / 充值记录
        self.detail_notebook = ttk.Notebook(parent, bootstyle="info")
        self.detail_notebook.pack(fill=BOTH, expand=YES)

        # Tab 1: 基本信息
        info_tab = ttk.Frame(self.detail_notebook, padding=10)
        self.detail_notebook.add(info_tab, text="基本信息")

        self.create_info_form(info_tab)

        # Tab 2: 充值记录
        recharge_tab = ttk.Frame(self.detail_notebook, padding=10)
        self.detail_notebook.add(recharge_tab, text="充值记录")

        self.create_recharge_form(recharge_tab)

    def create_info_form(self, parent):
        """创建基本信息表单"""
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=BOTH, expand=YES)

        # 名称
        row1 = ttk.Frame(form_frame)
        row1.pack(fill=X, pady=(0, 8))
        ttk.Label(row1, text="站点名称:", width=10).pack(side=LEFT)
        self.name_var = ttk.StringVar()
        ttk.Entry(row1, textvariable=self.name_var, width=30).pack(side=LEFT, fill=X, expand=YES)

        # URL
        row2 = ttk.Frame(form_frame)
        row2.pack(fill=X, pady=(0, 8))
        ttk.Label(row2, text="URL:", width=10).pack(side=LEFT)
        self.url_var = ttk.StringVar()
        ttk.Entry(row2, textvariable=self.url_var, width=30).pack(side=LEFT, fill=X, expand=YES)
        ttk.Button(row2, text="🌐", command=self.open_site_url, bootstyle="info-outline", width=3).pack(side=LEFT, padx=(5, 0))

        # 类型
        row3 = ttk.Frame(form_frame)
        row3.pack(fill=X, pady=(0, 8))
        ttk.Label(row3, text="站点类型:", width=10).pack(side=LEFT)
        self.type_var = ttk.StringVar(value=SITE_TYPE_PAID)
        type_combo = ttk.Combobox(row3, textvariable=self.type_var, width=15, state="readonly")
        type_combo['values'] = [f"{v} ({k})" for k, v in SITE_TYPE_LABELS.items()]
        type_combo.pack(side=LEFT)

        # 标签
        row4 = ttk.Frame(form_frame)
        row4.pack(fill=X, pady=(0, 8))
        ttk.Label(row4, text="标签:", width=10).pack(side=LEFT)
        self.tags_var = ttk.StringVar()
        ttk.Entry(row4, textvariable=self.tags_var, width=30).pack(side=LEFT, fill=X, expand=YES)
        ttk.Label(row4, text="(逗号分隔)", bootstyle="secondary", font=("Microsoft YaHei", 8)).pack(side=LEFT, padx=(5, 0))

        # API Key
        row4b = ttk.Frame(form_frame)
        row4b.pack(fill=X, pady=(0, 8))
        ttk.Label(row4b, text="API Key:", width=10).pack(side=LEFT)
        self.api_key_var = ttk.StringVar()
        self.api_key_entry = ttk.Entry(row4b, textvariable=self.api_key_var, width=30, show="*")
        self.api_key_entry.pack(side=LEFT, fill=X, expand=YES)
        self.api_key_show = False
        ttk.Button(row4b, text="👁", command=self.toggle_show_key, bootstyle="secondary-outline", width=3).pack(side=LEFT, padx=(5, 0))

        # 余额（可编辑）
        row5 = ttk.Frame(form_frame)
        row5.pack(fill=X, pady=(0, 8))
        ttk.Label(row5, text="当前余额:", width=10).pack(side=LEFT)
        self.balance_var = ttk.StringVar(value="0")
        ttk.Entry(row5, textvariable=self.balance_var, width=12).pack(side=LEFT)

        # 余额单位选择
        self.balance_unit_var = ttk.StringVar(value="USD")
        unit_combo = ttk.Combobox(row5, textvariable=self.balance_unit_var, width=8, state="readonly")
        unit_combo['values'] = ["USD", "CNY", "Token"]
        unit_combo.pack(side=LEFT, padx=(5, 0))
        ttk.Label(row5, text="(手动填写)", bootstyle="secondary", font=("Microsoft YaHei", 8)).pack(side=LEFT, padx=(8, 0))

        # 最后查询时间
        row6 = ttk.Frame(form_frame)
        row6.pack(fill=X, pady=(0, 8))
        ttk.Label(row6, text="最后查询:", width=10).pack(side=LEFT)
        self.last_query_label = ttk.Label(row6, text="-", bootstyle="secondary")
        self.last_query_label.pack(side=LEFT)

        # 备注
        row7 = ttk.Frame(form_frame)
        row7.pack(fill=X, pady=(0, 8))
        ttk.Label(row7, text="备注:", width=10).pack(side=LEFT, anchor=N)
        self.notes_text = ttk.Text(row7, height=3, width=30)
        self.notes_text.pack(side=LEFT, fill=X, expand=YES)

        # 签到网址
        row8 = ttk.Frame(form_frame)
        row8.pack(fill=X, pady=(0, 8))
        ttk.Label(row8, text="签到网址:", width=10).pack(side=LEFT)
        self.checkin_url_var = ttk.StringVar()
        ttk.Entry(row8, textvariable=self.checkin_url_var, width=30).pack(side=LEFT, fill=X, expand=YES)
        ttk.Button(row8, text="🔗", command=self.open_checkin_url, bootstyle="info-outline", width=3).pack(side=LEFT, padx=(5, 0))

        # 签到接口路径（用于 WAF 站点）
        row8b = ttk.Frame(form_frame)
        row8b.pack(fill=X, pady=(0, 8))
        ttk.Label(row8b, text="签到接口:", width=10).pack(side=LEFT)
        self.checkin_api_path_var = ttk.StringVar()
        ttk.Entry(row8b, textvariable=self.checkin_api_path_var, width=30).pack(side=LEFT, fill=X, expand=YES)
        ttk.Label(row8b, text="(默认 /api/user/checkin)", bootstyle="secondary", font=("Microsoft YaHei", 8)).pack(side=LEFT, padx=(5, 0))

        # Session Cookie（用于自动签到）
        row9 = ttk.Frame(form_frame)
        row9.pack(fill=X, pady=(0, 8))
        ttk.Label(row9, text="签到Cookie:", width=10).pack(side=LEFT)
        self.session_cookie_var = ttk.StringVar()
        self.cookie_entry = ttk.Entry(row9, textvariable=self.session_cookie_var, width=30, show="*")
        self.cookie_entry.pack(side=LEFT, fill=X, expand=YES)
        self.cookie_show = False
        ttk.Button(row9, text="👁", command=self.toggle_show_cookie, bootstyle="secondary-outline", width=3).pack(side=LEFT, padx=(3, 0))
        ttk.Button(row9, text="📋", command=self.copy_cookie_script, bootstyle="info-outline", width=3).pack(side=LEFT, padx=(3, 0))
        ttk.Button(row9, text="💰", command=self.query_balance_by_cookie, bootstyle="success-outline", width=3).pack(side=LEFT, padx=(3, 0))
        ttk.Button(row9, text="🎁", command=self.checkin_current_site, bootstyle="warning-outline", width=3).pack(side=LEFT, padx=(3, 0))

        # 签到额外 Headers（JSON）
        row9b_label = ttk.Frame(form_frame)
        row9b_label.pack(fill=X, pady=(0, 2))
        ttk.Label(row9b_label, text="签到Headers (JSON):").pack(side=LEFT)

        row9b = ttk.Frame(form_frame)
        row9b.pack(fill=X, pady=(0, 10))
        self.checkin_headers_text = Text(row9b, height=3, width=30)
        self.checkin_headers_text.pack(side=LEFT, fill=X, expand=YES)

        # Cookie 更新时间
        row9c_label = ttk.Frame(form_frame)
        row9c_label.pack(fill=X, pady=(0, 2))
        ttk.Label(row9c_label, text="Cookie 更新时间:").pack(side=LEFT)
        row9c = ttk.Frame(form_frame)
        row9c.pack(fill=X, pady=(0, 8))
        self.checkin_cookie_time_var = ttk.StringVar()
        ttk.Label(row9c, textvariable=self.checkin_cookie_time_var, bootstyle="secondary").pack(side=LEFT)

        # 签到 User ID（某些站点需要）
        row10 = ttk.Frame(form_frame)
        row10.pack(fill=X, pady=(0, 8))
        ttk.Label(row10, text="签到UserID:", width=10).pack(side=LEFT)
        self.checkin_user_id_var = ttk.StringVar()
        ttk.Entry(row10, textvariable=self.checkin_user_id_var, width=15).pack(side=LEFT)
        ttk.Label(row10, text="(部分站点需要)", bootstyle="secondary", font=("Microsoft YaHei", 8)).pack(side=LEFT, padx=(5, 0))

        # 保存按钮
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill=X, pady=(15, 0))
        ttk.Button(btn_frame, text="💾 保存修改", command=self.save_site, bootstyle="success", width=12).pack(side=RIGHT)

    def create_recharge_form(self, parent):
        """创建充值记录表单"""
        # 充值记录列表
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=BOTH, expand=YES)

        columns = ("date", "amount", "note")
        self.recharge_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8, bootstyle="info")
        self.recharge_tree.heading("date", text="日期")
        self.recharge_tree.heading("amount", text="金额")
        self.recharge_tree.heading("note", text="备注")

        self.recharge_tree.column("date", width=100)
        self.recharge_tree.column("amount", width=80)
        self.recharge_tree.column("note", width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.recharge_tree.yview)
        self.recharge_tree.configure(yscrollcommand=scrollbar.set)
        self.recharge_tree.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)

        # 添加充值记录
        add_frame = ttk.Labelframe(parent, text=" 添加充值记录 ", padding=10)
        add_frame.pack(fill=X, pady=(10, 0))

        input_row = ttk.Frame(add_frame)
        input_row.pack(fill=X)

        ttk.Label(input_row, text="金额:").pack(side=LEFT)
        self.recharge_amount_var = ttk.StringVar()
        ttk.Entry(input_row, textvariable=self.recharge_amount_var, width=10).pack(side=LEFT, padx=(5, 15))

        ttk.Label(input_row, text="日期:").pack(side=LEFT)
        self.recharge_date_var = ttk.StringVar()
        ttk.Entry(input_row, textvariable=self.recharge_date_var, width=12).pack(side=LEFT, padx=(5, 15))
        ttk.Label(input_row, text="(留空=今天)", bootstyle="secondary", font=("Microsoft YaHei", 8)).pack(side=LEFT)

        input_row2 = ttk.Frame(add_frame)
        input_row2.pack(fill=X, pady=(8, 0))

        ttk.Label(input_row2, text="备注:").pack(side=LEFT)
        self.recharge_note_var = ttk.StringVar()
        ttk.Entry(input_row2, textvariable=self.recharge_note_var, width=20).pack(side=LEFT, padx=(5, 15), fill=X, expand=YES)

        ttk.Button(input_row2, text="添加", command=self.add_recharge, bootstyle="success", width=8).pack(side=LEFT, padx=(10, 0))
        ttk.Button(input_row2, text="删除选中", command=self.delete_recharge, bootstyle="danger", width=8).pack(side=LEFT, padx=(5, 0))

    def create_charts_area(self, parent):
        """创建图表区域"""
        top_bar = ttk.Frame(parent)
        top_bar.pack(fill=X, pady=(0, 10))

        self.summary_label = ttk.Label(top_bar, text="", font=("Microsoft YaHei", 10))
        self.summary_label.pack(side=LEFT)

        ttk.Button(top_bar, text="📈 绘制图表", command=self.draw_charts, bootstyle="success", width=12).pack(side=RIGHT)

        charts_scroll_frame = ttk.Frame(parent)
        charts_scroll_frame.pack(fill=BOTH, expand=YES)

        canvas_container = ttk.Frame(charts_scroll_frame)
        canvas_container.pack(side=TOP, fill=BOTH, expand=YES)

        self.charts_canvas = tk.Canvas(canvas_container, highlightthickness=0, bd=0)
        self.charts_canvas.pack(side=LEFT, fill=BOTH, expand=YES)

        self.charts_y_scrollbar = ttk.Scrollbar(canvas_container, orient=VERTICAL, command=self.charts_canvas.yview)
        self.charts_y_scrollbar.pack(side=RIGHT, fill=Y)

        self.charts_x_scrollbar = ttk.Scrollbar(charts_scroll_frame, orient=HORIZONTAL, command=self.charts_canvas.xview)
        self.charts_x_scrollbar.pack(side=BOTTOM, fill=X, pady=(6, 0))

        self.charts_canvas.configure(
            xscrollcommand=self.charts_x_scrollbar.set,
            yscrollcommand=self.charts_y_scrollbar.set,
        )

        self._charts_min_width = 1120
        self.charts_content = ttk.Frame(self.charts_canvas)
        self.charts_content.columnconfigure(0, weight=1, minsize=540)
        self.charts_content.columnconfigure(1, weight=1, minsize=540)
        self.charts_content.rowconfigure(0, weight=1)
        self.charts_content.rowconfigure(1, weight=1)

        self.charts_window_id = self.charts_canvas.create_window(
            (0, 0),
            window=self.charts_content,
            anchor="nw",
            width=self._charts_min_width,
        )

        self.charts_content.bind("<Configure>", self.on_charts_content_configure)
        self.charts_canvas.bind("<Configure>", self.on_charts_canvas_configure)

        placeholder = "点击「绘制图表」生成统计图"

        balance_chart = ttk.Labelframe(self.charts_content, text=" 余额排名 ", padding=6)
        balance_chart.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
        self.balance_chart_label = ttk.Label(balance_chart, text=placeholder, bootstyle="secondary", anchor=CENTER, justify=CENTER)
        self.balance_chart_label.pack(fill=BOTH, expand=YES)

        type_chart = ttk.Labelframe(self.charts_content, text=" 类型占比与对比 ", padding=6)
        type_chart.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 6))
        self.type_chart_label = ttk.Label(type_chart, text=placeholder, bootstyle="secondary", anchor=CENTER, justify=CENTER)
        self.type_chart_label.pack(fill=BOTH, expand=YES)

        recharge_chart = ttk.Labelframe(self.charts_content, text=" 充值趋势（近12个月） ", padding=6)
        recharge_chart.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(6, 0))
        self.recharge_chart_label = ttk.Label(recharge_chart, text=placeholder, bootstyle="secondary", anchor=CENTER, justify=CENTER)
        self.recharge_chart_label.pack(fill=BOTH, expand=YES)

        checkin_chart = ttk.Labelframe(self.charts_content, text=" 签到活跃度（近30天） ", padding=6)
        checkin_chart.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(6, 0))
        self.checkin_chart_label = ttk.Label(checkin_chart, text=placeholder, bootstyle="secondary", anchor=CENTER, justify=CENTER)
        self.checkin_chart_label.pack(fill=BOTH, expand=YES)

    def on_charts_content_configure(self, event=None):
        """更新图表区域滚动范围"""
        if not hasattr(self, "charts_canvas"):
            return
        self.charts_canvas.configure(scrollregion=self.charts_canvas.bbox("all"))

    def on_charts_canvas_configure(self, event):
        """窗口宽度变化时，保持图表内容最小宽度以支持横向滚动"""
        if not hasattr(self, "charts_window_id"):
            return
        target_width = max(event.width, self._charts_min_width)
        self.charts_canvas.itemconfigure(self.charts_window_id, width=target_width)

    # ============ 事件处理 ============

    def refresh_site_list(self):
        """刷新站点列表"""
        self.stats_data = load_stats()

        # 如果没有站点列表组件，跳过
        if not hasattr(self, 'site_tree'):
            return

        self.site_tree.delete(*self.site_tree.get_children())

        for site in self.stats_data.get("sites", []):
            name = site.get("name", "未命名")
            site_type = SITE_TYPE_LABELS.get(site.get("type", SITE_TYPE_PAID), "付费站")
            balance = site.get("balance", 0)
            unit = site.get("balance_unit", "USD")

            if unit == "Token":
                balance_str = f"{balance:,.0f}"
            else:
                balance_str = f"${balance:.2f}"

            self.site_tree.insert("", "end", iid=site["id"], values=(name, site_type, balance_str))

    def on_site_select(self, event):
        """选中站点时加载详情"""
        selection = self.site_tree.selection()
        if not selection:
            return

        site_id = selection[0]
        self.current_site_id = site_id
        site = get_site_by_id(self.stats_data, site_id)

        if site:
            self.load_site_to_form(site)

    def load_site_to_form(self, site):
        """加载站点数据到表单"""
        self.name_var.set(site.get("name", ""))
        self.url_var.set(site.get("url", ""))

        # 类型
        site_type = site.get("type", SITE_TYPE_PAID)
        type_label = SITE_TYPE_LABELS.get(site_type, "付费站")
        self.type_var.set(f"{type_label} ({site_type})")

        # 标签
        tags = site.get("tags", [])
        self.tags_var.set(", ".join(tags))

        # API Key
        self.api_key_var.set(site.get("api_key", ""))

        # 余额
        balance = site.get("balance", 0)
        unit = site.get("balance_unit", "USD")
        self.balance_var.set(str(balance))
        self.balance_unit_var.set(unit)

        # 最后查询时间
        last_query = site.get("last_query_time", "")
        self.last_query_label.config(text=last_query or "从未查询")

        # 备注
        self.notes_text.delete("1.0", "end")
        self.notes_text.insert("1.0", site.get("notes", ""))

        # 签到网址
        self.checkin_url_var.set(site.get("checkin_url", ""))

        # 签到接口路径
        self.checkin_api_path_var.set(site.get("checkin_api_path", ""))

        # Session Cookie
        self.session_cookie_var.set(site.get("session_cookie", ""))

        # 签到额外 Headers
        self.checkin_headers_text.delete("1.0", "end")
        headers = site.get("checkin_headers", {})
        if isinstance(headers, dict) and headers:
            self.checkin_headers_text.insert("1.0", json.dumps(headers, ensure_ascii=False, indent=2))

        # Cookie 更新时间
        self.checkin_cookie_time_var.set(site.get("checkin_cookie_updated_at", ""))

        # 签到 User ID
        self.checkin_user_id_var.set(site.get("checkin_user_id", ""))

        # 充值记录
        self.refresh_recharge_list(site)

    def refresh_recharge_list(self, site):
        """刷新充值记录列表"""
        self.recharge_tree.delete(*self.recharge_tree.get_children())

        for record in site.get("recharge_records", []):
            date = record.get("date", "")
            amount = record.get("amount", 0)
            note = record.get("note", "")

            self.recharge_tree.insert("", "end", iid=record["id"], values=(date, f"${amount:.2f}", note))

    def save_site(self):
        """保存站点修改"""
        if not self.current_site_id:
            messagebox.showwarning("提示", "请先选择一个站点")
            return

        # 解析类型
        type_str = self.type_var.get()
        site_type = SITE_TYPE_PAID
        for k, v in SITE_TYPE_LABELS.items():
            if k in type_str:
                site_type = k
                break

        # 解析标签
        tags_str = self.tags_var.get().strip()
        tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

        # 解析余额
        try:
            balance = float(self.balance_var.get().strip() or "0")
        except ValueError:
            balance = 0
        balance_unit = self.balance_unit_var.get()

        # 解析签到 Headers（JSON）
        headers_text = self.checkin_headers_text.get("1.0", "end").strip()
        if headers_text:
            try:
                checkin_headers = json.loads(headers_text)
                if not isinstance(checkin_headers, dict):
                    messagebox.showwarning("提示", "签到Headers 必须是 JSON 对象")
                    return
            except json.JSONDecodeError:
                messagebox.showwarning("提示", "签到Headers JSON 格式错误")
                return
        else:
            checkin_headers = {}

        name = self.name_var.get().strip()
        url = self.url_var.get().strip()
        checkin_path = self.checkin_api_path_var.get().strip()

        if not name:
            messagebox.showwarning("提示", "站点名称不能为空")
            return
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            messagebox.showwarning("提示", "站点 URL 需要以 http:// 或 https:// 开头")
            return
        if checkin_path and not checkin_path.startswith("/"):
            messagebox.showwarning("提示", "签到接口路径需以 / 开头")
            return

        updates = {
            "name": name,
            "url": url,
            "type": site_type,
            "tags": tags,
            "api_key": self.api_key_var.get().strip(),
            "notes": self.notes_text.get("1.0", "end").strip(),
            "balance": balance,
            "balance_unit": balance_unit,
            "checkin_url": self.checkin_url_var.get().strip(),
            "checkin_api_path": checkin_path,
            "session_cookie": self.session_cookie_var.get().strip(),
            "checkin_headers": checkin_headers,
            "checkin_user_id": self.checkin_user_id_var.get().strip(),
        }

        # Cookie 更新时间：当 Cookie 变更时自动更新
        prev_site = get_site_by_id(self.stats_data, self.current_site_id)
        prev_cookie = (prev_site or {}).get("session_cookie", "") if prev_site else ""
        new_cookie = updates.get("session_cookie", "")
        if new_cookie and new_cookie != prev_cookie:
            updates["checkin_cookie_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            updates["checkin_cookie_updated_at"] = self.checkin_cookie_time_var.get().strip()

        if update_site(self.stats_data, self.current_site_id, updates):
            save_stats(self.stats_data)
            self.refresh_site_list()
            self.update_summary()
            # 通知主窗口刷新列表
            if self.on_save_callback:
                self.on_save_callback()
            messagebox.showinfo("成功", "站点信息已保存")
        else:
            messagebox.showerror("错误", "保存失败")

    def add_new_site(self):
        """添加新站点"""
        site = create_site(
            name="新站点",
            url="https://",
            site_type=SITE_TYPE_PAID
        )
        add_site(self.stats_data, site)
        save_stats(self.stats_data)
        self.refresh_site_list()
        self.update_summary()

        # 选中新站点
        self.site_tree.selection_set(site["id"])
        self.on_site_select(None)

    def delete_current_site(self):
        """删除当前选中的站点"""
        if not self.current_site_id:
            messagebox.showwarning("提示", "请先选择一个站点")
            return

        site = get_site_by_id(self.stats_data, self.current_site_id)
        if not site:
            return

        if messagebox.askyesno("确认删除", f"确定要删除站点「{site.get('name', '')}」吗？"):
            delete_site(self.stats_data, self.current_site_id)
            save_stats(self.stats_data)
            self.current_site_id = None
            self.refresh_site_list()
            self.update_summary()
            self.clear_form()

    def clear_form(self):
        """清空表单"""
        self.name_var.set("")
        self.url_var.set("")
        self.type_var.set(f"{SITE_TYPE_LABELS[SITE_TYPE_PAID]} ({SITE_TYPE_PAID})")
        self.tags_var.set("")
        self.api_key_var.set("")
        self.balance_var.set("0")
        self.balance_unit_var.set("USD")
        self.last_query_label.config(text="-")
        self.notes_text.delete("1.0", "end")
        self.checkin_url_var.set("")
        self.checkin_api_path_var.set("")
        self.session_cookie_var.set("")
        self.checkin_headers_text.delete("1.0", "end")
        self.checkin_cookie_time_var.set("")
        self.checkin_user_id_var.set("")
        if hasattr(self, 'recharge_tree'):
            self.recharge_tree.delete(*self.recharge_tree.get_children())

    def import_from_config(self):
        """从主配置导入站点"""
        if not self.profiles:
            messagebox.showinfo("提示", "没有可导入的配置")
            return

        new_sites = import_from_profiles(self.profiles, self.stats_data.get("sites", []))

        if not new_sites:
            messagebox.showinfo("提示", "所有配置已存在，无需导入")
            return

        for site in new_sites:
            add_site(self.stats_data, site)

        save_stats(self.stats_data)
        self.refresh_site_list()
        self.update_summary()
        messagebox.showinfo("成功", f"已导入 {len(new_sites)} 个站点")

    def open_site_url(self):
        """打开选中站点的网址"""
        if not self.current_site_id:
            messagebox.showwarning("提示", "请先选择一个站点")
            return

        site = get_site_by_id(self.stats_data, self.current_site_id)
        if site:
            url = site.get("url", "")
            if url:
                webbrowser.open(url)
            else:
                messagebox.showwarning("提示", "该站点没有配置网址")

    def open_checkin_url(self):
        """打开当前站点的签到网址"""
        checkin_url = self.checkin_url_var.get().strip()
        if checkin_url:
            webbrowser.open(checkin_url)
        else:
            messagebox.showwarning("提示", "该站点没有配置签到网址")

    def toggle_show_key(self):
        """切换显示/隐藏 API Key"""
        self.api_key_show = not self.api_key_show
        self.api_key_entry.config(show="" if self.api_key_show else "*")

    def toggle_show_cookie(self):
        """切换显示/隐藏 Cookie"""
        self.cookie_show = not self.cookie_show
        self.cookie_entry.config(show="" if self.cookie_show else "*")

    def query_balance_by_cookie(self):
        """使用 Cookie 查询余额"""
        url = self.url_var.get().strip()
        cookie = self.session_cookie_var.get().strip()
        user_id = self.checkin_user_id_var.get().strip()

        if not url:
            messagebox.showwarning("提示", "请先填写站点 URL")
            return
        if not cookie:
            messagebox.showwarning("提示", "请先填写签到 Cookie")
            return

        # 查询余额
        result = query_balance_by_cookie(url, cookie, user_id)

        if result.get("success"):
            balance = result.get("balance", 0)
            username = result.get("username", "")
            display_name = result.get("display_name", "")

            # 更新余额到表单
            self.balance_var.set(str(balance))
            self.balance_unit_var.set("USD")

            # 保存到站点数据
            if self.current_site_id:
                update_site(self.stats_data, self.current_site_id, {
                    "balance": balance,
                    "balance_unit": "USD"
                })
                save_stats(self.stats_data)
                self.refresh_site_list()
                self.update_summary()

            msg = f"查询成功！\n\n用户: {display_name or username}\n余额: ${balance:.2f}"
            messagebox.showinfo("Cookie 查询余额", msg)
        else:
            messagebox.showerror("查询失败", result.get("message", "未知错误"))

    def checkin_current_site(self):
        """当前站点单独签到"""
        if not self.current_site_id:
            messagebox.showwarning("提示", "请先选择一个站点")
            return

        site = get_site_by_id(self.stats_data, self.current_site_id)
        if not site:
            messagebox.showwarning("提示", "站点不存在")
            return

        base_url = site.get("url", "").strip()
        session_cookie = site.get("session_cookie", "").strip()
        user_id = site.get("checkin_user_id", "").strip()
        checkin_path = site.get("checkin_api_path", "/api/user/checkin")
        extra_headers = site.get("checkin_headers", {})
        if not isinstance(extra_headers, dict):
            extra_headers = {}

        if not base_url or not session_cookie:
            messagebox.showwarning("提示", "请先填写站点 URL 和 签到Cookie")
            return

        result = do_checkin(
            base_url,
            session_cookie,
            user_id,
            checkin_path=checkin_path,
            extra_headers=extra_headers,
        )

        if result.get("success"):
            quota = result.get("quota_awarded", 0)
            quota_usd = round(quota / 500000, 2) if quota else 0
            add_checkin_log(site.get("name", "未命名"), site.get("id", ""), True, quota_usd, result.get("message", ""))

            balance_result = query_balance_by_cookie(base_url, session_cookie, user_id)
            if balance_result.get("success"):
                new_balance = balance_result.get("balance", 0)
                update_site(self.stats_data, self.current_site_id, {"balance": new_balance, "balance_unit": "USD"})
                save_stats(self.stats_data)
                self.refresh_site_list()
                self.update_summary()

            if result.get("already_checked_in"):
                messagebox.showinfo("今日已签到", f"{site.get('name', '未命名')}\n{result.get('message', '今日已签到')}")
            else:
                messagebox.showinfo("签到成功", f"{site.get('name', '未命名')} 签到成功\n获得: ${quota_usd:.2f}")
        else:
            add_checkin_log(site.get("name", "未命名"), site.get("id", ""), False, 0, result.get("message", ""))
            messagebox.showerror("签到失败", result.get("message", "未知错误"))


    def copy_cookie_script(self):
        """打开网站并提示用户如何获取 Cookie"""
        # 打开网站
        url = self.url_var.get().strip()
        if url:
            webbrowser.open(url)

        # 弹出获取指南 + 粘贴窗口
        guide = (
            "请按以下步骤获取 Cookie：\n\n"
            "1. 在浏览器中登录网站\n"
            "2. 按 F12 打开开发者工具\n"
            "3. 切换到「网络」(Network) 标签\n"
            "4. 刷新页面 (F5)\n"
            "5. 右键点击任意请求\n"
            "6. 选择「复制」→「复制为 cURL (bash)」\n"
            "7. 粘贴到下方输入框并解析"
        )

        # 创建带「粘贴解析」按钮的对话框
        dialog = ttk.Toplevel(self.master)
        dialog.title("获取 Cookie")
        fit_toplevel(dialog, preferred_width=760, preferred_height=560, min_width=600, min_height=480)
        dialog.minsize(600, 480)
        dialog.transient(self.master)
        dialog.grab_set()

        ttk.Label(dialog, text=guide, justify=LEFT, font=("Microsoft YaHei", 10)).pack(padx=15, pady=10, anchor=W)

        input_frame = ttk.Frame(dialog)
        input_frame.pack(fill=BOTH, expand=YES, padx=15, pady=(0, 10))

        self.cookie_input_text = ScrolledText(input_frame, height=10, autohide=True)
        self.cookie_input_text.pack(fill=BOTH, expand=YES)

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=X, padx=15, pady=(0, 15))

        def paste_from_clipboard():
            """从剪贴板粘贴"""
            try:
                text = self.master.clipboard_get()
                self.cookie_input_text.text.delete("1.0", "end")
                self.cookie_input_text.text.insert("1.0", text)
            except Exception:
                messagebox.showwarning("提示", "剪贴板为空或无法读取")

        def parse_input():
            text = self.cookie_input_text.text.get("1.0", "end").strip()
            if not text:
                messagebox.showwarning("提示", "请输入或粘贴 cURL/请求内容")
                return
            self._parse_cookie_text(text)
            dialog.destroy()

        ttk.Button(btn_frame, text="📋 从剪贴板粘贴", command=paste_from_clipboard, bootstyle="info-outline", width=18).pack(side=LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="✅ 解析并填充", command=parse_input, bootstyle="success", width=15).pack(side=LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="关闭", command=dialog.destroy, bootstyle="secondary", width=10).pack(side=LEFT)

    def _parse_cookie_text(self, text):
        """解析粘贴的文本，提取 Cookie 和 UserID（支持 cURL 格式）"""
        import re

        cookie = ""
        user_id = ""
        extracted_headers = {}

        # 1. 尝试从 cURL 命令中提取 -b 'xxx' 或 --cookie 'xxx'
        curl_cookie = re.search(r"-b\s+['\"]([^'\"]+)['\"]", text)
        if not curl_cookie:
            curl_cookie = re.search(r"--cookie\s+['\"]([^'\"]+)['\"]", text)
        if curl_cookie:
            cookie = curl_cookie.group(1).strip()

        # 2. 尝试从 cURL 命令中提取 new-api-user header
        curl_uid = re.search(r"-H\s+['\"]new-api-user:\s*(\d+)['\"]", text, re.IGNORECASE)
        if curl_uid:
            user_id = curl_uid.group(1).strip()

        # 2.5 尝试从 cURL 命令中提取常用 Headers
        header_matches = re.findall(r"-H\s+['\"]([^'\"]+)['\"]", text)
        if header_matches:
            allowlist = {
                "user-agent",
                "referer",
                "origin",
                "accept",
                "accept-language",
                "sec-ch-ua",
                "sec-ch-ua-platform",
                "sec-ch-ua-mobile",
            }
            for h in header_matches:
                if ":" not in h:
                    continue
                k, v = h.split(":", 1)
                key = k.strip()
                val = v.strip()
                if key.lower() in allowlist:
                    extracted_headers[key] = val

        # 3. 如果不是 cURL 格式，尝试匹配 "Cookie: xxx" 格式
        if not cookie:
            cookie_match = re.search(r'Cookie[:\s]+([^\n]+)', text, re.IGNORECASE)
            if cookie_match:
                cookie = cookie_match.group(1).strip()

        # 4. 尝试匹配 "UserID: xxx" 格式
        if not user_id:
            uid_match = re.search(r'(?:UserID|new-api-user)[:\s]+(\d+)', text, re.IGNORECASE)
            if uid_match:
                user_id = uid_match.group(1).strip()

        # 5. 如果没匹配到，可能直接粘贴的就是 Cookie 值
        if not cookie and 'session=' in text:
            # 提取 session=xxx 部分
            session_match = re.search(r'(session=[^\s;]+)', text)
            if session_match:
                cookie = text.strip() if len(text) < 500 else session_match.group(1)

        # 填充到输入框
        if cookie:
            self.session_cookie_var.set(cookie)
            self.checkin_cookie_time_var.set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        if user_id:
            self.checkin_user_id_var.set(user_id)
        if extracted_headers:
            existing_headers = self.checkin_headers_text.get("1.0", "end").strip()
            if not existing_headers:
                self.checkin_headers_text.delete("1.0", "end")
                self.checkin_headers_text.insert("1.0", json.dumps(extracted_headers, ensure_ascii=False, indent=2))

        if cookie or user_id:
            msg = "已填充：\n"
            if cookie:
                display_cookie = cookie[:60] + '...' if len(cookie) > 60 else cookie
                msg += f"• Cookie: {display_cookie}\n"
            if user_id:
                msg += f"• UserID: {user_id}"
            if extracted_headers:
                msg += f"\n• Headers: {len(extracted_headers)} 项"
            messagebox.showinfo("解析成功", msg)
        else:
            messagebox.showwarning("解析失败", "未能识别 Cookie 或 UserID\n\n请确保复制了 cURL 命令或 Cookie 内容")

    def open_site_url(self):
        """打开当前站点的网址"""
        url = self.url_var.get().strip()
        if url:
            webbrowser.open(url)
        else:
            messagebox.showwarning("提示", "该站点没有配置网址")

    def add_recharge(self):
        """添加充值记录"""
        if not self.current_site_id:
            messagebox.showwarning("提示", "请先选择一个站点")
            return

        try:
            amount = float(self.recharge_amount_var.get().strip())
            if amount <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showwarning("提示", "请输入有效的金额")
            return

        date = self.recharge_date_var.get().strip() or None
        note = self.recharge_note_var.get().strip()

        site = get_site_by_id(self.stats_data, self.current_site_id)
        if site:
            add_recharge_record(site, amount, date, note)
            save_stats(self.stats_data)
            self.refresh_recharge_list(site)
            self.update_summary()

            # 清空输入
            self.recharge_amount_var.set("")
            self.recharge_date_var.set("")
            self.recharge_note_var.set("")

    def delete_recharge(self):
        """删除选中的充值记录"""
        if not self.current_site_id:
            return

        selection = self.recharge_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一条充值记录")
            return

        record_id = selection[0]
        site = get_site_by_id(self.stats_data, self.current_site_id)

        if site and delete_recharge_record(site, record_id):
            save_stats(self.stats_data)
            self.refresh_recharge_list(site)
            self.update_summary()

    def update_summary(self):
        """更新统计摘要（不绘制图表）"""
        sites = self.stats_data.get("sites", [])
        summary = get_stats_summary(sites)
        summary_text = f"📊 共 {summary['total_sites']} 个站点 | 💵 总余额 ${summary['total_balance_usd']:.2f} | 💰 总充值 ${summary['total_recharge']:.2f}"
        self.summary_label.config(text=summary_text)

    def draw_charts(self):
        """绘制图表（点击按钮时才执行）"""
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        import matplotlib.pyplot as plt

        sites = self.stats_data.get("sites", [])

        chart_jobs = [
            (self.balance_chart_label, lambda: create_balance_bar_chart(sites, figsize=(4.8, 2.6), dpi=110)),
            (self.type_chart_label, lambda: create_type_stats_chart(sites, figsize=(4.8, 2.6), dpi=110)),
            (self.recharge_chart_label, lambda: create_recharge_trend_chart(sites, months=12, figsize=(4.8, 2.6), dpi=110)),
            (self.checkin_chart_label, lambda: create_checkin_activity_chart(days=30, figsize=(4.8, 2.6), dpi=110)),
        ]

        for chart_label, factory in chart_jobs:
            fig = None
            try:
                fig = factory()
                chart_img = self.fig_to_image(fig, FigureCanvasAgg)
                chart_label.config(image=chart_img, text="")
                chart_label.image = chart_img
            except Exception as e:
                chart_label.config(image="", text=f"图表生成失败: {e}")
                chart_label.image = None
            finally:
                if fig is not None:
                    plt.close(fig)

        self.charts_loaded = True

    def fig_to_image(self, fig, FigureCanvasAgg):
        """将 matplotlib Figure 转换为 tkinter 可用的图片"""
        canvas = FigureCanvasAgg(fig)
        canvas.draw()

        buf = io.BytesIO()
        canvas.print_png(buf)
        buf.seek(0)

        img = Image.open(buf)
        return ImageTk.PhotoImage(img)


class StatsDialog:
    """统计模块弹窗（兼容旧接口）"""

    def __init__(self, parent, profiles=None):
        """
        Args:
            parent: 父窗口
            profiles: 主配置中的 profiles 列表（用于导入）
        """
        self.parent = parent
        self.profiles = profiles or []

        self.dialog = ttk.Toplevel(parent)
        self.dialog.title("📊 站点统计")
        fit_toplevel(self.dialog, preferred_width=1180, preferred_height=820, min_width=900, min_height=640)
        self.dialog.resizable(True, True)

        # 设置窗口图标
        try:
            self.dialog.iconbitmap(resource_path("assets/icon.ico"))
        except Exception:
            pass

        self.dialog.transient(parent)

        # 嵌入 StatsFrame
        self.stats_frame = StatsFrame(self.dialog, profiles=profiles)
        self.stats_frame.pack(fill=BOTH, expand=YES)
