"""
统计模块 GUI - 站点档案管理弹窗
"""
import io
import webbrowser
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledFrame
from tkinter import messagebox
from PIL import Image, ImageTk

from konata_api.utils import resource_path
from konata_api.stats import (
    load_stats, save_stats, create_site, add_site, update_site, delete_site,
    get_site_by_id, add_recharge_record, delete_recharge_record,
    import_from_profiles, get_stats_summary,
    create_balance_bar_chart, create_type_stats_chart,
    SITE_TYPE_PAID, SITE_TYPE_FREE, SITE_TYPE_SUBSCRIPTION, SITE_TYPE_LABELS
)


class StatsDialog:
    """统计模块主弹窗"""

    def __init__(self, parent, profiles=None):
        """
        Args:
            parent: 父窗口
            profiles: 主配置中的 profiles 列表（用于导入）
        """
        self.parent = parent
        self.profiles = profiles or []
        self.stats_data = load_stats()
        self.current_site_id = None
        self.charts_loaded = False  # 图表是否已加载

        self.dialog = ttk.Toplevel(parent)
        self.dialog.title("📊 站点统计")
        self.dialog.geometry("1100x750")
        self.dialog.resizable(True, True)

        # 设置窗口图标
        try:
            self.dialog.iconbitmap(resource_path("assets/icon.ico"))
        except:
            pass

        self.dialog.transient(parent)

        self.create_widgets()
        self.refresh_site_list()
        self.update_summary()

    def create_widgets(self):
        """创建主界面"""
        # 使用 ScrolledFrame 包裹整个内容
        self.scroll_frame = ScrolledFrame(self.dialog, autohide=True)
        self.scroll_frame.pack(fill=BOTH, expand=YES)

        main_frame = ttk.Frame(self.scroll_frame, padding=10)
        main_frame.pack(fill=BOTH, expand=YES)

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
        ttk.Entry(row4b, textvariable=self.api_key_var, width=30, show="*").pack(side=LEFT, fill=X, expand=YES)

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

        # 保存按钮
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill=X, pady=(15, 0))
        ttk.Button(btn_frame, text="保存修改", command=self.save_site, bootstyle="success", width=12).pack(side=RIGHT)

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
        # 顶部：统计摘要 + 绘制按钮
        top_bar = ttk.Frame(parent)
        top_bar.pack(fill=X, pady=(0, 10))

        self.summary_label = ttk.Label(top_bar, text="", font=("Microsoft YaHei", 10))
        self.summary_label.pack(side=LEFT)

        ttk.Button(top_bar, text="📈 绘制图表", command=self.draw_charts, bootstyle="success", width=12).pack(side=RIGHT)

        # 图表区域
        charts_frame = ttk.Frame(parent)
        charts_frame.pack(fill=BOTH, expand=YES)

        # 左图：余额柱状图
        left_chart = ttk.Frame(charts_frame)
        left_chart.pack(side=LEFT, fill=BOTH, expand=YES, padx=(0, 5))

        self.balance_chart_label = ttk.Label(left_chart, text="点击「绘制图表」生成统计图", bootstyle="secondary", font=("Microsoft YaHei", 10))
        self.balance_chart_label.pack(fill=BOTH, expand=YES)

        # 右图：分类统计图
        right_chart = ttk.Frame(charts_frame)
        right_chart.pack(side=LEFT, fill=BOTH, expand=YES, padx=(5, 0))

        self.type_chart_label = ttk.Label(right_chart, text="点击「绘制图表」生成统计图", bootstyle="secondary", font=("Microsoft YaHei", 10))
        self.type_chart_label.pack(fill=BOTH, expand=YES)

    # ============ 事件处理 ============

    def refresh_site_list(self):
        """刷新站点列表"""
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
            messagebox.showwarning("提示", "请先选择一个站点", parent=self.dialog)
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

        updates = {
            "name": self.name_var.get().strip(),
            "url": self.url_var.get().strip(),
            "type": site_type,
            "tags": tags,
            "api_key": self.api_key_var.get().strip(),
            "notes": self.notes_text.get("1.0", "end").strip(),
            "balance": balance,
            "balance_unit": balance_unit
        }

        if update_site(self.stats_data, self.current_site_id, updates):
            save_stats(self.stats_data)
            self.refresh_site_list()
            self.update_summary()
            messagebox.showinfo("成功", "站点信息已保存", parent=self.dialog)
        else:
            messagebox.showerror("错误", "保存失败", parent=self.dialog)

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
            messagebox.showwarning("提示", "请先选择一个站点", parent=self.dialog)
            return

        site = get_site_by_id(self.stats_data, self.current_site_id)
        if not site:
            return

        if messagebox.askyesno("确认删除", f"确定要删除站点「{site.get('name', '')}」吗？", parent=self.dialog):
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
        self.recharge_tree.delete(*self.recharge_tree.get_children())

    def import_from_config(self):
        """从主配置导入站点"""
        if not self.profiles:
            messagebox.showinfo("提示", "没有可导入的配置", parent=self.dialog)
            return

        new_sites = import_from_profiles(self.profiles, self.stats_data.get("sites", []))

        if not new_sites:
            messagebox.showinfo("提示", "所有配置已存在，无需导入", parent=self.dialog)
            return

        for site in new_sites:
            add_site(self.stats_data, site)

        save_stats(self.stats_data)
        self.refresh_site_list()
        self.update_summary()
        messagebox.showinfo("成功", f"已导入 {len(new_sites)} 个站点", parent=self.dialog)

    def open_site_url(self):
        """打开选中站点的网址"""
        if not self.current_site_id:
            messagebox.showwarning("提示", "请先选择一个站点", parent=self.dialog)
            return

        site = get_site_by_id(self.stats_data, self.current_site_id)
        if site:
            url = site.get("url", "")
            if url:
                webbrowser.open(url)
            else:
                messagebox.showwarning("提示", "该站点没有配置网址", parent=self.dialog)

    def add_recharge(self):
        """添加充值记录"""
        if not self.current_site_id:
            messagebox.showwarning("提示", "请先选择一个站点", parent=self.dialog)
            return

        try:
            amount = float(self.recharge_amount_var.get().strip())
            if amount <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showwarning("提示", "请输入有效的金额", parent=self.dialog)
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
            messagebox.showwarning("提示", "请先选择一条充值记录", parent=self.dialog)
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
        # 延迟导入 matplotlib，避免启动时卡顿
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        sites = self.stats_data.get("sites", [])

        # 生成余额柱状图
        try:
            fig1 = create_balance_bar_chart(sites, figsize=(5, 3), dpi=100)
            img1 = self.fig_to_image(fig1, FigureCanvasAgg)
            self.balance_chart_label.config(image=img1, text="")
            self.balance_chart_label.image = img1
            fig1.clear()
        except Exception as e:
            self.balance_chart_label.config(text=f"图表生成失败: {e}")

        # 生成分类统计图
        try:
            fig2 = create_type_stats_chart(sites, figsize=(5, 3), dpi=100)
            img2 = self.fig_to_image(fig2, FigureCanvasAgg)
            self.type_chart_label.config(image=img2, text="")
            self.type_chart_label.image = img2
            fig2.clear()
        except Exception as e:
            self.type_chart_label.config(text=f"图表生成失败: {e}")

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
