"""
站点测试模块 - 连通性测试、真伪性测试、对话功能
"""
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText
import httpx

from konata_api.stats import load_stats, get_site_by_id
from konata_api.conversation_test import (
    test_connectivity,
    detect_model,
    MODEL_LIST,
)
from konata_api.api_presets import (
    API_PRESETS,
    PRESET_LIST,
    DEFAULT_MODELS,
    build_request,
)
from konata_api.utils import resource_path


class TestDialog(ttkb.Toplevel):
    """站点测试对话框"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent)
        self.title("站点测试")
        self.geometry("900x650")
        self.minsize(800, 550)

        # 设置窗口图标
        try:
            self.iconbitmap(resource_path("assets/icon.ico"))
        except Exception:
            pass

        # 当前选中的站点
        self.current_site: Optional[dict] = None

        # 测试状态
        self.is_testing = False

        # 思考模式开关
        self.with_thinking = tk.BooleanVar(value=True)
        self.show_thinking = tk.BooleanVar(value=True)

        # System 字段开关（某些中转站不允许发送 system）
        self.with_system = tk.BooleanVar(value=True)

        # 模型选择
        self.selected_model = tk.StringVar(value=MODEL_LIST[0][0])

        # 接口预设
        self.selected_preset = tk.StringVar(value="anthropic_relay")
        self.api_config = {}  # 自定义配置

        self._create_widgets()
        self._load_sites()

    def _create_widgets(self):
        """创建界面组件"""
        # 主容器
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=BOTH, expand=YES)

        # 左右分栏
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(0, weight=1)

        # ========== 左侧：站点列表 ==========
        left_frame = ttk.LabelFrame(main_frame, text="站点列表", padding=5)
        left_frame.grid(row=0, column=0, sticky=NSEW, padx=(0, 5))
        left_frame.rowconfigure(0, weight=1)
        left_frame.columnconfigure(0, weight=1)

        # 站点列表 Treeview
        columns = ("name", "url")
        self.site_tree = ttk.Treeview(
            left_frame, columns=columns, show="headings", height=20
        )
        self.site_tree.heading("name", text="站点名称")
        self.site_tree.heading("url", text="URL")
        self.site_tree.column("name", width=100)
        self.site_tree.column("url", width=150)
        self.site_tree.grid(row=0, column=0, sticky=NSEW)

        # 滚动条
        scrollbar = ttk.Scrollbar(
            left_frame, orient=VERTICAL, command=self.site_tree.yview
        )
        scrollbar.grid(row=0, column=1, sticky=NS)
        self.site_tree.configure(yscrollcommand=scrollbar.set)

        # 绑定选择事件
        self.site_tree.bind("<<TreeviewSelect>>", self._on_site_select)

        # 刷新按钮
        ttk.Button(
            left_frame, text="🔄 刷新列表", command=self._load_sites, bootstyle="info-outline"
        ).grid(row=1, column=0, columnspan=2, pady=(5, 0), sticky=EW)

        # ========== 右侧：测试面板 ==========
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky=NSEW)
        right_frame.rowconfigure(2, weight=1)
        right_frame.columnconfigure(0, weight=1)

        # --- 站点信息 ---
        info_frame = ttk.LabelFrame(right_frame, text="当前站点", padding=5)
        info_frame.grid(row=0, column=0, sticky=EW, pady=(0, 5))
        info_frame.columnconfigure(1, weight=1)

        ttk.Label(info_frame, text="名称:").grid(row=0, column=0, sticky=W, padx=(0, 5))
        self.lbl_site_name = ttk.Label(info_frame, text="未选择", font=("", 10, "bold"))
        self.lbl_site_name.grid(row=0, column=1, sticky=W)

        ttk.Label(info_frame, text="URL:").grid(row=1, column=0, sticky=W, padx=(0, 5))
        self.lbl_site_url = ttk.Label(info_frame, text="-", foreground="gray")
        self.lbl_site_url.grid(row=1, column=1, sticky=W)

        # --- 测试控制 ---
        ctrl_frame = ttk.LabelFrame(right_frame, text="测试控制", padding=5)
        ctrl_frame.grid(row=1, column=0, sticky=EW, pady=(0, 5))

        # 第一行：测试按钮
        btn_row1 = ttk.Frame(ctrl_frame)
        btn_row1.pack(fill=X, pady=(0, 5))

        self.btn_connectivity = ttk.Button(
            btn_row1, text="🔗 连通性测试", command=self._test_connectivity,
            bootstyle="info", width=14
        )
        self.btn_connectivity.pack(side=LEFT, padx=(0, 5))

        self.btn_authenticity = ttk.Button(
            btn_row1, text="🔍 真伪性测试", command=self._test_authenticity,
            bootstyle="warning", width=14
        )
        self.btn_authenticity.pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            btn_row1, text="🗑️ 清空", command=self._clear_output,
            bootstyle="secondary-outline", width=14
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            btn_row1, text="⚙️ 设置", command=self._open_settings,
            bootstyle="dark-outline", width=8
        ).pack(side=LEFT)

        # 第二行：接口预设和模型选择
        btn_row2 = ttk.Frame(ctrl_frame)
        btn_row2.pack(fill=X, pady=(0, 5))

        ttk.Label(btn_row2, text="接口:").pack(side=LEFT, padx=(0, 5))
        self.preset_combo = ttk.Combobox(
            btn_row2, textvariable=self.selected_preset, width=20, state="readonly"
        )
        self.preset_combo["values"] = [name for _, name in PRESET_LIST]
        self.preset_combo.current(0)
        self.preset_combo.pack(side=LEFT, padx=(0, 10))
        self.preset_combo.bind("<<ComboboxSelected>>", self._on_preset_change)

        ttk.Label(btn_row2, text="模型:").pack(side=LEFT, padx=(0, 5))
        self.model_combo = ttk.Combobox(
            btn_row2, textvariable=self.selected_model, width=28
        )
        self.model_combo["values"] = [mid for mid, name in MODEL_LIST]
        self.model_combo.current(0)
        self.model_combo.pack(side=LEFT)

        # 第三行：思考模式
        btn_row3 = ttk.Frame(ctrl_frame)
        btn_row3.pack(fill=X)

        ttk.Checkbutton(
            btn_row3, text="思考模式", variable=self.with_thinking, bootstyle="round-toggle"
        ).pack(side=LEFT, padx=(0, 10))

        ttk.Checkbutton(
            btn_row3, text="显示思考", variable=self.show_thinking, bootstyle="round-toggle"
        ).pack(side=LEFT, padx=(0, 15))

        ttk.Separator(btn_row3, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=(0, 15))

        ttk.Checkbutton(
            btn_row3, text="发送 System", variable=self.with_system, bootstyle="round-toggle"
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Label(
            btn_row3, text="(关闭可解决部分中转站报错)", foreground="gray", font=("", 8)
        ).pack(side=LEFT)

        # --- 输出区域 ---
        output_frame = ttk.LabelFrame(right_frame, text="输出", padding=5)
        output_frame.grid(row=2, column=0, sticky=NSEW, pady=(0, 5))
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)

        self.output_text = ScrolledText(output_frame, height=15, autohide=True)
        self.output_text.grid(row=0, column=0, sticky=NSEW)

        # --- 对话区域 ---
        chat_frame = ttk.LabelFrame(right_frame, text="对话", padding=5)
        chat_frame.grid(row=3, column=0, sticky=EW)
        chat_frame.columnconfigure(0, weight=1)

        self.chat_entry = ttk.Entry(chat_frame)
        self.chat_entry.grid(row=0, column=0, sticky=EW, padx=(0, 5))
        self.chat_entry.bind("<Return>", lambda e: self._send_chat())

        self.btn_send = ttk.Button(
            chat_frame, text="发送", command=self._send_chat, bootstyle="success", width=8
        )
        self.btn_send.grid(row=0, column=1)

    def _load_sites(self):
        """加载站点列表"""
        # 清空现有项
        for item in self.site_tree.get_children():
            self.site_tree.delete(item)

        # 从 stats.json 加载
        stats_data = load_stats()
        sites = stats_data.get("sites", [])

        for site in sites:
            self.site_tree.insert(
                "", END,
                iid=site["id"],
                values=(site.get("name", "未命名"), site.get("url", ""))
            )

        if not sites:
            self._append_output("⚠️ 站点列表为空，请先在统计模块中添加站点\n")

    def _on_site_select(self, event):
        """站点选择事件"""
        selection = self.site_tree.selection()
        if not selection:
            return

        site_id = selection[0]
        stats_data = load_stats()
        site = get_site_by_id(stats_data, site_id)

        if site:
            self.current_site = site
            self.lbl_site_name.config(text=site.get("name", "未命名"))
            self.lbl_site_url.config(text=site.get("url", "-"))

    def _get_api_key(self) -> str:
        """获取当前站点的 API Key"""
        if not self.current_site:
            return ""

        # 优先从站点数据获取 API Key
        api_key = self.current_site.get("api_key", "")
        if api_key:
            return api_key

        # 兼容：从配置文件中查找对应的 API Key
        from konata_api.utils import load_config
        config = load_config()
        site_url = self.current_site.get("url", "").rstrip("/")

        for profile in config.get("profiles", []):
            if profile.get("url", "").rstrip("/") == site_url:
                return profile.get("api_key", "")
        return ""

    def _append_output(self, text: str):
        """追加输出文本（线程安全）"""
        def _append():
            self.output_text.text.config(state="normal")
            self.output_text.text.insert(END, text)
            self.output_text.text.see(END)
            self.output_text.text.config(state="disabled")
        self.after(0, _append)

    def _clear_output(self):
        """清空输出"""
        self.output_text.text.config(state="normal")
        self.output_text.text.delete("1.0", END)
        self.output_text.text.config(state="disabled")

    def _set_testing(self, testing: bool):
        """设置测试状态"""
        self.is_testing = testing
        state = "disabled" if testing else "normal"
        self.btn_connectivity.config(state=state)
        self.btn_authenticity.config(state=state)
        self.btn_send.config(state=state)

    def _on_preset_change(self, event=None):
        """接口预设切换"""
        idx = self.preset_combo.current()
        if idx >= 0 and idx < len(PRESET_LIST):
            preset_id, _ = PRESET_LIST[idx]
            self.selected_preset.set(preset_id)

            # 更新模型列表
            if "anthropic" in preset_id:
                models = DEFAULT_MODELS.get("anthropic", [])
            else:
                models = DEFAULT_MODELS.get("openai", [])
            self.model_combo["values"] = [m[0] for m in models]
            if models:
                self.selected_model.set(models[0][0])

    def _open_settings(self):
        """打开设置对话框"""
        from konata_api.test_settings_dialog import TestSettingsDialog

        def on_save(config):
            self.api_config = config
            # 更新模型
            if config.get("model"):
                self.selected_model.set(config["model"])

        TestSettingsDialog(self, current_config=self.api_config, on_save=on_save)

    def _get_current_preset_id(self) -> str:
        """获取当前预设 ID"""
        idx = self.preset_combo.current()
        if idx >= 0 and idx < len(PRESET_LIST):
            return PRESET_LIST[idx][0]
        return "anthropic_relay"

    def _send_request_with_preset(self, url: str, api_key: str, message: str,
                                   on_thinking=None, on_text=None, on_status=None) -> str:
        """使用当前预设发送请求"""
        model = self.selected_model.get()
        preset_id = self._get_current_preset_id()
        with_thinking = self.with_thinking.get()
        with_system = self.with_system.get()

        # 构建请求
        if self.api_config:
            # 使用自定义配置
            full_url, headers, body = build_request(
                "custom", url, api_key, model, message,
                with_thinking=with_thinking,
                with_system=with_system,
                custom_config=self.api_config
            )
        else:
            full_url, headers, body = build_request(
                preset_id, url, api_key, model, message,
                with_thinking=with_thinking,
                with_system=with_system
            )

        if full_url is None:
            if on_status:
                on_status(f"❌ 配置错误: {body}")
            return ""

        if on_status:
            on_status(f"🔗 连接中: {full_url}")

        full_response = ""

        try:
            with httpx.Client(timeout=600.0) as client:
                with client.stream("POST", full_url, headers=headers, json=body) as response:
                    if response.status_code != 200:
                        error = response.read().decode('utf-8')
                        if on_status:
                            on_status(f"❌ 请求失败 [{response.status_code}]: {error}")
                        return ""

                    if on_status:
                        on_status("✅ 连接成功，等待响应...")

                    # 判断响应格式
                    is_anthropic = "anthropic" in preset_id or (self.api_config and "/v1/messages" in self.api_config.get("endpoint", ""))

                    if is_anthropic:
                        full_response = self._parse_anthropic_stream(response, on_thinking, on_text, on_status)
                    else:
                        full_response = self._parse_openai_stream(response, on_text, on_status)

            return full_response

        except httpx.ConnectError:
            if on_status:
                on_status("❌ 连接失败: 无法连接到服务器")
            return ""
        except httpx.TimeoutException:
            if on_status:
                on_status("❌ 请求超时")
            return ""
        except Exception as e:
            if on_status:
                on_status(f"❌ 请求异常: {e}")
            return ""

    def _parse_anthropic_stream(self, response, on_thinking, on_text, on_status) -> str:
        """解析 Anthropic 流式响应"""
        full_response = ""
        in_thinking = False
        buffer = ""

        for chunk in response.iter_bytes():
            buffer += chunk.decode('utf-8', errors='ignore')

            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.strip()

                if not line.startswith("data: "):
                    continue

                data = line[6:]
                if data == "[DONE]":
                    break

                try:
                    event = json.loads(data)
                    event_type = event.get("type", "")

                    if event_type == "content_block_start":
                        block = event.get("content_block", {})
                        if block.get("type") == "thinking":
                            in_thinking = True
                            if on_status:
                                on_status("[💭 思考中...]")
                        elif block.get("type") == "text":
                            if in_thinking:
                                in_thinking = False
                            if on_status:
                                on_status("[💬 回复中...]")

                    elif event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            full_response += text
                            if on_text:
                                on_text(text)
                        elif delta.get("type") == "thinking_delta":
                            if on_thinking:
                                on_thinking(delta.get("thinking", ""))

                    elif event_type == "message_start":
                        usage = event.get("message", {}).get("usage", {})
                        if usage and on_status:
                            on_status(f"[📊 输入 tokens: {usage.get('input_tokens', 'N/A')}]")

                    elif event_type == "message_delta":
                        usage = event.get("usage", {})
                        if usage and on_status:
                            on_status(f"[📊 输出 tokens: {usage.get('output_tokens', 'N/A')}]")

                except json.JSONDecodeError:
                    pass

        return full_response

    def _parse_openai_stream(self, response, on_text, on_status) -> str:
        """解析 OpenAI 流式响应"""
        full_response = ""
        buffer = ""

        for chunk in response.iter_bytes():
            buffer += chunk.decode('utf-8', errors='ignore')

            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.strip()

                if not line.startswith("data: "):
                    continue

                data = line[6:]
                if data == "[DONE]":
                    break

                try:
                    event = json.loads(data)
                    choices = event.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_response += content
                            if on_text:
                                on_text(content)

                except json.JSONDecodeError:
                    pass

        return full_response

    def _test_connectivity(self):
        """连通性测试"""
        if not self.current_site:
            messagebox.showwarning("提示", "请先选择一个站点")
            return

        url = self.current_site.get("url", "")
        api_key = self._get_api_key()

        self._clear_output()
        self._append_output(f"🔗 测试连通性: {url}\n")
        if api_key:
            self._append_output(f"🔑 API Key: {api_key[:8]}...{api_key[-4:]}\n")
        self._append_output("-" * 40 + "\n")

        self._set_testing(True)

        def _run():
            result = test_connectivity(url, api_key)
            self._append_output(f"\n结果: {result['message']}\n")

            if result.get("latency_ms"):
                self._append_output(f"延迟: {result['latency_ms']:.1f} ms\n")

            # 显示可用模型列表
            models = result.get("models", [])
            if models:
                self._append_output(f"\n📦 可用模型 ({len(models)}个):\n")
                for model in models:
                    self._append_output(f"  • {model}\n")

            self._append_output("-" * 40 + "\n")
            self.after(0, lambda: self._set_testing(False))

        threading.Thread(target=_run, daemon=True).start()

    def _test_authenticity(self):
        """真伪性测试"""
        if not self.current_site:
            messagebox.showwarning("提示", "请先选择一个站点")
            return

        api_key = self._get_api_key()
        if not api_key:
            messagebox.showwarning("提示", "未找到该站点的 API Key，请确保配置文件中有对应的配置")
            return

        url = self.current_site.get("url", "")
        model_id = self.selected_model.get()
        preset_id = self._get_current_preset_id()

        self._clear_output()
        self._append_output(f"🔍 真伪性测试: {url}\n")
        self._append_output(f"📦 使用模型: {model_id}\n")
        self._append_output(f"🔌 接口预设: {preset_id}\n")
        self._append_output("-" * 40 + "\n")

        self._set_testing(True)

        def on_thinking(text):
            if self.show_thinking.get():
                self._append_output(text)

        def on_text(text):
            self._append_output(text)

        def on_status(text):
            self._append_output(f"{text}\n")

        def _run():
            self._append_output("🔍 开始模型真伪检测...\n")
            self._append_output("原理: 通过询问知识库截止时间判断真实模型\n\n")

            response = self._send_request_with_preset(
                url, api_key, "你的知识库截止时间？",
                on_thinking=on_thinking,
                on_text=on_text,
                on_status=on_status,
            )

            if response:
                detected = detect_model(response)
                self._append_output(f"\n\n{'=' * 40}\n")
                self._append_output(f"🎯 检测结果: {detected}\n")
                if detected != "未知模型":
                    self._append_output("✅ 模型已识别 (准确率约 95%)\n")
                else:
                    self._append_output("⚠️ 无法自动识别，请根据回复内容手动判断\n")
                self._append_output(f"{'=' * 40}\n")
            else:
                self._append_output("\n❌ 检测失败：未获取到响应\n")

            self.after(0, lambda: self._set_testing(False))

        threading.Thread(target=_run, daemon=True).start()

    def _send_chat(self):
        """发送对话"""
        if not self.current_site:
            messagebox.showwarning("提示", "请先选择一个站点")
            return

        message = self.chat_entry.get().strip()
        if not message:
            return

        api_key = self._get_api_key()
        if not api_key:
            messagebox.showwarning("提示", "未找到该站点的 API Key")
            return

        url = self.current_site.get("url", "")

        self.chat_entry.delete(0, END)
        self._append_output(f"\n👤 你: {message}\n")
        self._append_output("-" * 40 + "\n")

        self._set_testing(True)

        def on_thinking(text):
            if self.show_thinking.get():
                self._append_output(text)

        def on_text(text):
            self._append_output(text)

        def on_status(text):
            self._append_output(f"{text}\n")

        def _run():
            self._send_request_with_preset(
                url, api_key, message,
                on_thinking=on_thinking,
                on_text=on_text,
                on_status=on_status,
            )
            self._append_output("\n" + "-" * 40 + "\n")
            self.after(0, lambda: self._set_testing(False))

        threading.Thread(target=_run, daemon=True).start()

