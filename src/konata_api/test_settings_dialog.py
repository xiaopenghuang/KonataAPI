"""
站点测试设置对话框 - 专业版
选择预设后直接显示对应的请求头和请求体
"""
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from typing import Optional, Callable

import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText

from konata_api.api_presets import (
    API_PRESETS,
    PRESET_LIST,
    DEFAULT_MODELS,
    get_preset,
    get_custom_presets,
    save_custom_preset,
    delete_custom_preset,
    export_presets,
    import_presets,
    build_request,
)
from konata_api.utils import resource_path


class TestSettingsDialog(ttkb.Toplevel):
    """站点测试设置对话框"""

    def __init__(self, parent, current_config: dict = None, on_save: Callable = None, **kwargs):
        super().__init__(parent)
        self.title("接口设置")
        self.geometry("950x700")
        self.minsize(900, 650)

        try:
            self.iconbitmap(resource_path("assets/icon.ico"))
        except Exception:
            pass

        self.on_save = on_save
        self.current_config = current_config or {}

        # 当前选中的预设
        self.selected_preset_id = self.current_config.get("preset_id", "anthropic_relay")
        self.custom_model = tk.StringVar(value=self.current_config.get("model", "claude-sonnet-4-5-20250929"))

        # 编辑模式
        self.edit_mode = tk.BooleanVar(value=False)

        self._create_widgets()
        self._refresh_preset_list()
        self._select_preset_by_id(self.selected_preset_id)

    def _create_widgets(self):
        """创建界面"""
        # 主容器
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=BOTH, expand=YES)

        # 左右分栏
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=3)
        main_frame.rowconfigure(0, weight=1)

        # ========== 左侧：预设列表 ==========
        left_frame = ttk.LabelFrame(main_frame, text="接口预设", padding=5)
        left_frame.grid(row=0, column=0, sticky=NSEW, padx=(0, 10))
        left_frame.rowconfigure(0, weight=1)
        left_frame.columnconfigure(0, weight=1)

        # 预设列表
        self.preset_listbox = tk.Listbox(left_frame, width=25, exportselection=False)
        self.preset_listbox.grid(row=0, column=0, sticky=NSEW)
        self.preset_listbox.bind("<<ListboxSelect>>", self._on_preset_select)

        # 滚动条
        scrollbar = ttk.Scrollbar(left_frame, orient=VERTICAL, command=self.preset_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky=NS)
        self.preset_listbox.configure(yscrollcommand=scrollbar.set)

        # 按钮
        btn_frame = ttk.Frame(left_frame)
        btn_frame.grid(row=1, column=0, columnspan=2, sticky=EW, pady=(5, 0))
        ttk.Button(btn_frame, text="新建", command=self._new_custom, bootstyle="success-outline", width=8).pack(side=LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="删除", command=self._delete_custom, bootstyle="danger-outline", width=8).pack(side=LEFT)

        # 导入导出
        btn_frame2 = ttk.Frame(left_frame)
        btn_frame2.grid(row=2, column=0, columnspan=2, sticky=EW, pady=(5, 0))
        ttk.Button(btn_frame2, text="导入", command=self._import_config, bootstyle="info-outline", width=8).pack(side=LEFT, padx=(0, 5))
        ttk.Button(btn_frame2, text="导出", command=self._export_config, bootstyle="info-outline", width=8).pack(side=LEFT)

        # ========== 右侧：预设详情 ==========
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky=NSEW)
        right_frame.rowconfigure(2, weight=1)
        right_frame.rowconfigure(3, weight=2)
        right_frame.columnconfigure(0, weight=1)

        # --- 基本信息 ---
        info_frame = ttk.LabelFrame(right_frame, text="基本信息", padding=10)
        info_frame.grid(row=0, column=0, sticky=EW, pady=(0, 10))
        info_frame.columnconfigure(1, weight=1)

        # 名称
        ttk.Label(info_frame, text="名称:", width=10).grid(row=0, column=0, sticky=W, pady=2)
        self.lbl_name = ttk.Label(info_frame, text="-", font=("", 10, "bold"))
        self.lbl_name.grid(row=0, column=1, sticky=W, pady=2)

        # 描述
        ttk.Label(info_frame, text="描述:", width=10).grid(row=1, column=0, sticky=W, pady=2)
        self.lbl_desc = ttk.Label(info_frame, text="-", foreground="gray")
        self.lbl_desc.grid(row=1, column=1, sticky=W, pady=2)

        # 端点
        ttk.Label(info_frame, text="端点:", width=10).grid(row=2, column=0, sticky=W, pady=2)
        self.lbl_endpoint = ttk.Label(info_frame, text="-", foreground="blue")
        self.lbl_endpoint.grid(row=2, column=1, sticky=W, pady=2)

        # 认证方式
        ttk.Label(info_frame, text="认证方式:", width=10).grid(row=3, column=0, sticky=W, pady=2)
        self.lbl_auth = ttk.Label(info_frame, text="-")
        self.lbl_auth.grid(row=3, column=1, sticky=W, pady=2)

        # 思考模式
        ttk.Label(info_frame, text="思考模式:", width=10).grid(row=4, column=0, sticky=W, pady=2)
        self.lbl_thinking = ttk.Label(info_frame, text="-")
        self.lbl_thinking.grid(row=4, column=1, sticky=W, pady=2)

        # --- 模型选择 ---
        model_frame = ttk.LabelFrame(right_frame, text="模型设置", padding=10)
        model_frame.grid(row=1, column=0, sticky=EW, pady=(0, 10))

        model_row = ttk.Frame(model_frame)
        model_row.pack(fill=X)
        ttk.Label(model_row, text="模型:").pack(side=LEFT, padx=(0, 10))
        self.model_combo = ttk.Combobox(model_row, textvariable=self.custom_model, width=40)
        self.model_combo.pack(side=LEFT, fill=X, expand=YES)
        ttk.Label(model_frame, text="可直接输入自定义模型 ID", foreground="gray", font=("", 8)).pack(anchor=W, pady=(5, 0))

        # --- 请求头 ---
        headers_frame = ttk.LabelFrame(right_frame, text="请求头 (Headers)", padding=5)
        headers_frame.grid(row=2, column=0, sticky=NSEW, pady=(0, 10))
        headers_frame.rowconfigure(0, weight=1)
        headers_frame.columnconfigure(0, weight=1)

        self.headers_text = ScrolledText(headers_frame, height=8, autohide=True)
        self.headers_text.grid(row=0, column=0, sticky=NSEW)

        # --- 请求体 ---
        body_frame = ttk.LabelFrame(right_frame, text="请求体模板 (Body) - 使用 {model} 和 {message} 作为占位符", padding=5)
        body_frame.grid(row=3, column=0, sticky=NSEW, pady=(0, 10))
        body_frame.rowconfigure(0, weight=1)
        body_frame.columnconfigure(0, weight=1)

        self.body_text = ScrolledText(body_frame, height=12, autohide=True)
        self.body_text.grid(row=0, column=0, sticky=NSEW)

        # --- 底部按钮 ---
        bottom_frame = ttk.Frame(right_frame)
        bottom_frame.grid(row=4, column=0, sticky=EW)

        # 左侧：编辑模式开关
        ttk.Checkbutton(
            bottom_frame, text="编辑模式", variable=self.edit_mode,
            command=self._toggle_edit_mode, bootstyle="round-toggle"
        ).pack(side=LEFT)

        ttk.Button(
            bottom_frame, text="格式化 JSON", command=self._format_json,
            bootstyle="info-outline"
        ).pack(side=LEFT, padx=(10, 0))

        ttk.Button(
            bottom_frame, text="预览请求", command=self._preview_request,
            bootstyle="warning-outline"
        ).pack(side=LEFT, padx=(10, 0))

        # 右侧：保存取消
        ttk.Button(
            bottom_frame, text="取消", command=self.destroy,
            bootstyle="secondary"
        ).pack(side=RIGHT, padx=(5, 0))

        ttk.Button(
            bottom_frame, text="保存配置", command=self._save_config,
            bootstyle="success"
        ).pack(side=RIGHT)

        # 初始状态：只读
        self._toggle_edit_mode()

    def _refresh_preset_list(self):
        """刷新预设列表"""
        self.preset_listbox.delete(0, END)

        # 内置预设
        for preset_id, name in PRESET_LIST:
            if preset_id != "custom":
                self.preset_listbox.insert(END, f"📦 {name}")

        # 自定义预设
        for custom in get_custom_presets():
            self.preset_listbox.insert(END, f"✏️ {custom.get('name', '未命名')}")

    def _select_preset_by_id(self, preset_id: str):
        """根据 ID 选中预设"""
        # 查找内置预设
        for i, (pid, _) in enumerate(PRESET_LIST):
            if pid == preset_id and pid != "custom":
                self.preset_listbox.selection_clear(0, END)
                self.preset_listbox.selection_set(i)
                self.preset_listbox.see(i)
                self._load_preset(preset_id)
                return

        # 查找自定义预设
        customs = get_custom_presets()
        builtin_count = len([p for p in PRESET_LIST if p[0] != "custom"])
        for i, custom in enumerate(customs):
            if custom.get("id") == preset_id:
                idx = builtin_count + i
                self.preset_listbox.selection_clear(0, END)
                self.preset_listbox.selection_set(idx)
                self.preset_listbox.see(idx)
                self._load_custom_preset(custom)
                return

        # 默认选第一个
        if self.preset_listbox.size() > 0:
            self.preset_listbox.selection_set(0)
            self._on_preset_select(None)

    def _on_preset_select(self, event):
        """预设选择事件"""
        selection = self.preset_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        builtin_presets = [p for p in PRESET_LIST if p[0] != "custom"]
        builtin_count = len(builtin_presets)

        if idx < builtin_count:
            preset_id, _ = builtin_presets[idx]
            self.selected_preset_id = preset_id
            self._load_preset(preset_id)
        else:
            # 自定义预设
            custom_idx = idx - builtin_count
            customs = get_custom_presets()
            if custom_idx < len(customs):
                custom = customs[custom_idx]
                self.selected_preset_id = custom.get("id", "custom")
                self._load_custom_preset(custom)

    def _load_preset(self, preset_id: str):
        """加载内置预设"""
        preset = get_preset(preset_id)
        if not preset:
            return

        self.lbl_name.config(text=preset.get("name", "-"))
        self.lbl_desc.config(text=preset.get("description", "-"))
        self.lbl_endpoint.config(text=preset.get("endpoint", "-"))

        auth = f"{preset.get('auth_header', 'Authorization')}: {preset.get('auth_prefix', '')}***"
        self.lbl_auth.config(text=auth)

        thinking = "✅ 支持" if preset.get("supports_thinking") else "❌ 不支持"
        self.lbl_thinking.config(text=thinking)

        # 更新模型列表
        if "anthropic" in preset_id:
            models = DEFAULT_MODELS.get("anthropic", [])
        else:
            models = DEFAULT_MODELS.get("openai", [])
        self.model_combo["values"] = [m[0] for m in models]

        # 更新代码显示
        self._update_code_display(preset)

    def _load_custom_preset(self, custom: dict):
        """加载自定义预设"""
        self.lbl_name.config(text=f"[自定义] {custom.get('name', '未命名')}")
        self.lbl_desc.config(text=custom.get("description", "-"))
        self.lbl_endpoint.config(text=custom.get("endpoint", "-"))

        auth = f"{custom.get('auth_header', 'Authorization')}: {custom.get('auth_prefix', '')}***"
        self.lbl_auth.config(text=auth)

        thinking = "✅ 支持" if custom.get("supports_thinking") else "❌ 不支持"
        self.lbl_thinking.config(text=thinking)

        self._update_code_display(custom)

    def _update_code_display(self, config: dict):
        """更新代码显示"""
        # 请求头
        headers = config.get("headers", {})
        self.headers_text.text.config(state="normal")
        self.headers_text.text.delete("1.0", END)
        self.headers_text.text.insert("1.0", json.dumps(headers, indent=2, ensure_ascii=False))

        # 请求体
        body = config.get("body_template", {})

        # 如果支持思考模式，合并显示
        if config.get("supports_thinking") and config.get("thinking_config"):
            body_with_thinking = {**body, **config.get("thinking_config", {})}
            body_text = json.dumps(body, indent=2, ensure_ascii=False)
            body_text += "\n\n// 思考模式配置 (启用时追加):\n"
            body_text += json.dumps(config.get("thinking_config", {}), indent=2, ensure_ascii=False)
        else:
            body_text = json.dumps(body, indent=2, ensure_ascii=False)

        self.body_text.text.config(state="normal")
        self.body_text.text.delete("1.0", END)
        self.body_text.text.insert("1.0", body_text)

        # 根据编辑模式设置状态
        if not self.edit_mode.get():
            self.headers_text.text.config(state="disabled")
            self.body_text.text.config(state="disabled")

    def _toggle_edit_mode(self):
        """切换编辑模式"""
        if self.edit_mode.get():
            self.headers_text.text.config(state="normal")
            self.body_text.text.config(state="normal")
        else:
            self.headers_text.text.config(state="disabled")
            self.body_text.text.config(state="disabled")

    def _format_json(self):
        """格式化 JSON"""
        if not self.edit_mode.get():
            messagebox.showinfo("提示", "请先开启编辑模式")
            return

        try:
            # 格式化请求头
            headers_content = self.headers_text.text.get("1.0", END).strip()
            if headers_content:
                headers_data = json.loads(headers_content)
                self.headers_text.text.delete("1.0", END)
                self.headers_text.text.insert("1.0", json.dumps(headers_data, indent=2, ensure_ascii=False))

            # 格式化请求体（去掉注释部分）
            body_content = self.body_text.text.get("1.0", END).strip()
            if body_content:
                # 移除注释行
                lines = body_content.split('\n')
                json_lines = [l for l in lines if not l.strip().startswith('//')]
                clean_content = '\n'.join(json_lines)

                # 可能有多个 JSON 对象，只取第一个
                try:
                    body_data = json.loads(clean_content)
                    self.body_text.text.delete("1.0", END)
                    self.body_text.text.insert("1.0", json.dumps(body_data, indent=2, ensure_ascii=False))
                except json.JSONDecodeError:
                    # 尝试解析第一个完整的 JSON
                    pass

            messagebox.showinfo("成功", "JSON 已格式化")
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON 错误", f"JSON 格式错误: {e}")

    def _preview_request(self):
        """预览请求"""
        # 弹出预览对话框
        preview_dialog = ttkb.Toplevel(self)
        preview_dialog.title("请求预览")
        preview_dialog.geometry("700x600")

        try:
            preview_dialog.iconbitmap(resource_path("assets/icon.ico"))
        except:
            pass

        frame = ttk.Frame(preview_dialog, padding=10)
        frame.pack(fill=BOTH, expand=YES)

        # 输入参数
        param_frame = ttk.LabelFrame(frame, text="测试参数", padding=10)
        param_frame.pack(fill=X, pady=(0, 10))

        row1 = ttk.Frame(param_frame)
        row1.pack(fill=X, pady=2)
        ttk.Label(row1, text="URL:", width=10).pack(side=LEFT)
        url_entry = ttk.Entry(row1)
        url_entry.pack(side=LEFT, fill=X, expand=YES)
        url_entry.insert(0, "https://api.example.com")

        row2 = ttk.Frame(param_frame)
        row2.pack(fill=X, pady=2)
        ttk.Label(row2, text="API Key:", width=10).pack(side=LEFT)
        key_entry = ttk.Entry(row2, show="*")
        key_entry.pack(side=LEFT, fill=X, expand=YES)
        key_entry.insert(0, "sk-your-api-key")

        row3 = ttk.Frame(param_frame)
        row3.pack(fill=X, pady=2)
        ttk.Label(row3, text="消息:", width=10).pack(side=LEFT)
        msg_entry = ttk.Entry(row3)
        msg_entry.pack(side=LEFT, fill=X, expand=YES)
        msg_entry.insert(0, "你的知识库截止时间？")

        # 预览输出
        output_text = ScrolledText(frame, height=20, autohide=True)
        output_text.pack(fill=BOTH, expand=YES, pady=(0, 10))

        def generate():
            try:
                url = url_entry.get().strip()
                api_key = key_entry.get().strip()
                message = msg_entry.get().strip()
                model = self.custom_model.get().strip()

                # 获取当前配置
                config = self._get_current_config()

                full_url, headers, body = build_request(
                    "custom", url, api_key, model, message,
                    with_thinking=config.get("supports_thinking", False),
                    custom_config=config
                )

                if full_url is None:
                    output_text.text.delete("1.0", END)
                    output_text.text.insert("1.0", f"错误: {body}")
                    return

                preview = f"=== 请求 URL ===\n{full_url}\n\n"
                preview += f"=== 请求方法 ===\nPOST\n\n"
                preview += f"=== 请求头 ===\n{json.dumps(headers, indent=2, ensure_ascii=False)}\n\n"
                preview += f"=== 请求体 ===\n{json.dumps(body, indent=2, ensure_ascii=False)}\n"

                output_text.text.delete("1.0", END)
                output_text.text.insert("1.0", preview)

            except Exception as e:
                output_text.text.delete("1.0", END)
                output_text.text.insert("1.0", f"错误: {e}")

        ttk.Button(frame, text="生成预览", command=generate, bootstyle="info").pack()

    def _get_current_config(self) -> dict:
        """获取当前配置"""
        # 解析请求头
        try:
            headers_content = self.headers_text.text.get("1.0", END).strip()
            headers = json.loads(headers_content) if headers_content else {}
        except json.JSONDecodeError:
            headers = {}

        # 解析请求体
        try:
            body_content = self.body_text.text.get("1.0", END).strip()
            # 移除注释
            lines = body_content.split('\n')
            json_lines = [l for l in lines if not l.strip().startswith('//')]
            clean_content = '\n'.join(json_lines)
            body = json.loads(clean_content) if clean_content else {}
        except json.JSONDecodeError:
            body = {}

        # 获取当前预设的其他配置
        preset = get_preset(self.selected_preset_id)
        if preset:
            endpoint = preset.get("endpoint", "/v1/messages")
            auth_header = preset.get("auth_header", "Authorization")
            auth_prefix = preset.get("auth_prefix", "Bearer ")
            supports_thinking = preset.get("supports_thinking", False)
            thinking_config = preset.get("thinking_config", {})
        else:
            # 自定义预设
            customs = get_custom_presets()
            custom = next((c for c in customs if c.get("id") == self.selected_preset_id), None)
            if custom:
                endpoint = custom.get("endpoint", "/v1/messages")
                auth_header = custom.get("auth_header", "Authorization")
                auth_prefix = custom.get("auth_prefix", "Bearer ")
                supports_thinking = custom.get("supports_thinking", False)
                thinking_config = custom.get("thinking_config", {})
            else:
                endpoint = "/v1/messages"
                auth_header = "Authorization"
                auth_prefix = "Bearer "
                supports_thinking = False
                thinking_config = {}

        return {
            "endpoint": endpoint,
            "headers": headers,
            "body_template": body,
            "auth_header": auth_header,
            "auth_prefix": auth_prefix,
            "supports_thinking": supports_thinking,
            "thinking_config": thinking_config,
        }

    def _new_custom(self):
        """新建自定义配置"""
        name = simpledialog.askstring("新建配置", "请输入配置名称:", parent=self)
        if not name:
            return

        import uuid
        custom_id = f"custom_{uuid.uuid4().hex[:8]}"

        # 基于当前预设创建
        preset = get_preset(self.selected_preset_id)
        if not preset:
            preset = API_PRESETS.get("anthropic_relay", {})

        custom = {
            "id": custom_id,
            "name": name,
            "description": f"基于 {preset.get('name', '未知')} 创建",
            "endpoint": preset.get("endpoint", "/v1/messages"),
            "headers": preset.get("headers", {}),
            "body_template": preset.get("body_template", {}),
            "auth_header": preset.get("auth_header", "Authorization"),
            "auth_prefix": preset.get("auth_prefix", "Bearer "),
            "supports_thinking": preset.get("supports_thinking", False),
            "thinking_config": preset.get("thinking_config", {}),
        }

        if save_custom_preset(custom):
            self._refresh_preset_list()
            self._select_preset_by_id(custom_id)
            messagebox.showinfo("成功", "自定义配置已创建")
        else:
            messagebox.showerror("错误", "保存失败")

    def _delete_custom(self):
        """删除自定义配置"""
        selection = self.preset_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        builtin_count = len([p for p in PRESET_LIST if p[0] != "custom"])

        if idx < builtin_count:
            messagebox.showwarning("提示", "内置预设不能删除")
            return

        custom_idx = idx - builtin_count
        customs = get_custom_presets()
        if custom_idx >= len(customs):
            return

        custom = customs[custom_idx]
        if messagebox.askyesno("确认", f"确定删除配置 '{custom.get('name', '未命名')}'？"):
            if delete_custom_preset(custom.get("id")):
                self._refresh_preset_list()
                if self.preset_listbox.size() > 0:
                    self.preset_listbox.selection_set(0)
                    self._on_preset_select(None)
                messagebox.showinfo("成功", "配置已删除")
            else:
                messagebox.showerror("错误", "删除失败")

    def _import_config(self):
        """导入配置"""
        file_path = filedialog.askopenfilename(
            title="选择配置文件",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
            parent=self
        )
        if not file_path:
            return

        success, msg = import_presets(file_path)
        if success:
            self._refresh_preset_list()
            messagebox.showinfo("成功", msg)
        else:
            messagebox.showerror("错误", msg)

    def _export_config(self):
        """导出配置"""
        file_path = filedialog.asksaveasfilename(
            title="保存配置文件",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
            parent=self
        )
        if not file_path:
            return

        if export_presets(file_path):
            messagebox.showinfo("成功", f"配置已导出到:\n{file_path}")
        else:
            messagebox.showerror("错误", "导出失败")

    def _save_config(self):
        """保存配置"""
        config = {
            "preset_id": self.selected_preset_id,
            "model": self.custom_model.get(),
        }

        # 如果开启了编辑模式，保存编辑的内容
        if self.edit_mode.get():
            config.update(self._get_current_config())

        if self.on_save:
            self.on_save(config)

        self.destroy()
