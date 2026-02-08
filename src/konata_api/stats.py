"""
统计模块 - 站点档案管理与图表生成
"""
import json
import os
import uuid
import warnings
from datetime import datetime, timedelta
from typing import Optional

# 过滤 matplotlib 字体警告
warnings.filterwarnings('ignore', message='Glyph .* missing from')

import matplotlib
matplotlib.use('Agg')  # 非交互式后端，避免 tkinter 冲突
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import FuncFormatter

# 设置中文字体（在导入后立即设置）
FONT_FAMILY_STACK = [
    "Times New Roman",  # English
    "SimSun",           # Chinese (宋体)
    "DejaVu Serif",     # fallback
]

FONT_DEFAULT = FontProperties(family=FONT_FAMILY_STACK, size=10)
FONT_SMALL = FontProperties(family=FONT_FAMILY_STACK, size=9)
FONT_TITLE = FontProperties(family=FONT_FAMILY_STACK, size=12, weight="bold")
FONT_SUBTITLE = FontProperties(family=FONT_FAMILY_STACK, size=11, weight="bold")

plt.rcParams["font.family"] = FONT_FAMILY_STACK
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.facecolor"] = "#f8fafc"
plt.rcParams["axes.facecolor"] = "#f8fafc"
plt.rcParams["savefig.facecolor"] = "#f8fafc"

from konata_api.utils import get_exe_dir


# 站点类型常量
SITE_TYPE_PAID = "paid"           # 付费站
SITE_TYPE_FREE = "free"           # 公益站
SITE_TYPE_SUBSCRIPTION = "subscription"  # 订阅转API

SITE_TYPE_LABELS = {
    SITE_TYPE_PAID: "付费站",
    SITE_TYPE_FREE: "公益站",
    SITE_TYPE_SUBSCRIPTION: "订阅转API",
}


def get_stats_path() -> str:
    """获取统计数据文件路径"""
    return os.path.join(get_exe_dir(), "config", "stats.json")


def get_checkin_log_path() -> str:
    """获取签到日志文件路径"""
    return os.path.join(get_exe_dir(), "config", "checkin_log.json")


def load_checkin_log() -> list:
    """加载签到日志"""
    path = get_checkin_log_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_checkin_log(logs: list) -> bool:
    """保存签到日志"""
    path = get_checkin_log_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False


def add_checkin_log(site_name: str, site_id: str, success: bool, quota_awarded: float = 0, message: str = "") -> dict:
    """
    添加签到日志记录

    Args:
        site_name: 站点名称
        site_id: 站点ID
        success: 是否成功
        quota_awarded: 获得的额度
        message: 提示信息

    Returns:
        新增的日志记录
    """
    logs = load_checkin_log()
    record = {
        "id": f"chk-{uuid.uuid4().hex[:6]}",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "site_name": site_name,
        "site_id": site_id,
        "success": success,
        "quota_awarded": quota_awarded,
        "message": message,
    }
    logs.insert(0, record)  # 最新的在前面
    # 只保留最近 500 条
    logs = logs[:500]
    save_checkin_log(logs)
    return record


def get_today_checkin_sites() -> set:
    """获取今天已签到的站点ID集合"""
    logs = load_checkin_log()
    today = datetime.now().strftime("%Y-%m-%d")
    return {log["site_id"] for log in logs if log.get("time", "").startswith(today) and log.get("success")}


def load_stats() -> dict:
    """加载统计数据"""
    path = get_stats_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"sites": []}


def save_stats(data: dict) -> bool:
    """保存统计数据"""
    path = get_stats_path()
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False


def generate_site_id() -> str:
    """生成站点唯一ID"""
    return str(uuid.uuid4())[:8]


def generate_record_id() -> str:
    """生成充值记录唯一ID"""
    return f"rec-{uuid.uuid4().hex[:6]}"


def create_site(
    name: str,
    url: str,
    site_type: str = SITE_TYPE_PAID,
    tags: list = None,
    balance: float = 0,
    balance_unit: str = "USD",
    notes: str = "",
    api_key: str = ""
) -> dict:
    """创建新站点档案"""
    return {
        "id": generate_site_id(),
        "name": name,
        "url": url,
        "type": site_type,
        "tags": tags or [],
        "balance": balance,
        "balance_unit": balance_unit,
        "last_query_time": "",
        "notes": notes,
        "api_key": api_key,
        "recharge_records": []
    }


def add_site(data: dict, site: dict) -> dict:
    """添加站点到数据"""
    data["sites"].append(site)
    return data


def update_site(data: dict, site_id: str, updates: dict) -> bool:
    """更新站点信息"""
    for site in data["sites"]:
        if site["id"] == site_id:
            site.update(updates)
            return True
    return False


def delete_site(data: dict, site_id: str) -> bool:
    """删除站点"""
    for i, site in enumerate(data["sites"]):
        if site["id"] == site_id:
            data["sites"].pop(i)
            return True
    return False


def get_site_by_id(data: dict, site_id: str) -> Optional[dict]:
    """根据ID获取站点"""
    for site in data["sites"]:
        if site["id"] == site_id:
            return site
    return None


def add_recharge_record(site: dict, amount: float, date: str = None, note: str = "") -> dict:
    """添加充值记录"""
    record = {
        "id": generate_record_id(),
        "amount": amount,
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "note": note
    }
    site["recharge_records"].append(record)
    return record


def delete_recharge_record(site: dict, record_id: str) -> bool:
    """删除充值记录"""
    for i, record in enumerate(site.get("recharge_records", [])):
        if record["id"] == record_id:
            site["recharge_records"].pop(i)
            return True
    return False


def import_from_profiles(profiles: list, existing_sites: list) -> list:
    """
    从配置文件的 profiles 导入站点
    返回新导入的站点列表
    """
    existing_urls = {site["url"] for site in existing_sites}
    new_sites = []

    for profile in profiles:
        url = profile.get("url", "").rstrip("/")
        if not url or url in existing_urls:
            continue

        site = create_site(
            name=profile.get("name", "未命名"),
            url=url,
            site_type=SITE_TYPE_PAID,  # 默认付费站
            tags=[],
            balance=0,
            balance_unit="USD",
            notes="",
            api_key=profile.get("api_key", "")
        )
        new_sites.append(site)
        existing_urls.add(url)

    return new_sites


def update_site_balance(data: dict, url: str, balance: float, unit: str = "USD"):
    """根据 URL 更新站点余额（查询后自动调用）"""
    url = url.rstrip("/")
    for site in data["sites"]:
        if site["url"].rstrip("/") == url:
            site["balance"] = balance
            site["balance_unit"] = unit
            site["last_query_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return True
    return False


# ============ 图表生成 ============

def _create_placeholder_chart(message: str, figsize=(6, 4), dpi=100) -> Figure:
    """Create a simple placeholder chart when no data is available."""
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.text(0.5, 0.5, message, ha="center", va="center", color="#64748b", fontproperties=FONT_SUBTITLE)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.tight_layout()
    return fig


def _set_axis_style(ax, grid_axis: str = "x"):
    """Apply a unified modern style to axes."""
    ax.grid(axis=grid_axis, linestyle="--", linewidth=0.8, color="#cbd5e1", alpha=0.6)
    ax.tick_params(colors="#334155", labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")



def _apply_tick_font(ax):
    for tick in ax.get_xticklabels():
        tick.set_fontproperties(FONT_SMALL)
    for tick in ax.get_yticklabels():
        tick.set_fontproperties(FONT_SMALL)



def _shorten_name(name: str, max_len: int = 14) -> str:
    if len(name) <= max_len:
        return name
    return name[: max_len - 3] + "..."



def _parse_datetime(value: str):
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y/%m/%d %H:%M:%S",
    )
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None



def _iter_recent_month_keys(months: int = 12):
    cursor = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    keys = []
    for _ in range(max(months, 1)):
        keys.append(cursor.strftime("%Y-%m"))
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    return list(reversed(keys))



def create_balance_bar_chart(sites: list, figsize=(6, 4), dpi=100) -> Figure:
    """Generate a horizontal ranking chart for site balances."""
    valid_sites = [
        s for s in sites
        if s.get("balance", 0) > 0 and s.get("balance_unit") in ("USD", "CNY", "")
    ]
    valid_sites = sorted(valid_sites, key=lambda x: x.get("balance", 0), reverse=True)[:10]

    if not valid_sites:
        return _create_placeholder_chart("暂无余额数据", figsize=figsize, dpi=dpi)

    names = [_shorten_name(s.get("name", "未命名")) for s in valid_sites]
    balances = [float(s.get("balance", 0) or 0) for s in valid_sites]

    color_map = {
        SITE_TYPE_PAID: "#3b82f6",
        SITE_TYPE_FREE: "#10b981",
        SITE_TYPE_SUBSCRIPTION: "#f59e0b",
    }
    colors = [color_map.get(s.get("type", SITE_TYPE_PAID), "#94a3b8") for s in valid_sites]

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    y_labels = list(reversed(names))
    y_values = list(reversed(balances))
    y_colors = list(reversed(colors))

    bars = ax.barh(y_labels, y_values, color=y_colors, edgecolor="white", linewidth=1.0, height=0.58)

    max_val = max(y_values) if y_values else 1.0
    for bar, value in zip(bars, y_values):
        ax.text(
            bar.get_width() + max_val * 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"${value:,.2f}",
            va="center",
            ha="left",
            color="#1f2937",
            fontproperties=FONT_SMALL,
        )

    ax.set_title("余额排名 Top 10", fontproperties=FONT_TITLE, color="#0f172a", pad=10)
    ax.set_xlabel("Balance (USD)", fontproperties=FONT_DEFAULT, color="#334155")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.set_xlim(0, max_val * 1.24)

    _set_axis_style(ax, grid_axis="x")
    _apply_tick_font(ax)

    fig.tight_layout()
    return fig



def create_type_stats_chart(sites: list, figsize=(6, 4), dpi=100) -> Figure:
    """Generate type proportion and type balance comparison charts."""
    type_stats = {}
    for site in sites:
        site_type = site.get("type", SITE_TYPE_PAID)
        if site_type not in type_stats:
            type_stats[site_type] = {"count": 0, "balance": 0.0}
        type_stats[site_type]["count"] += 1
        if site.get("balance_unit") in ("USD", "CNY", ""):
            type_stats[site_type]["balance"] += float(site.get("balance", 0) or 0)

    if not type_stats:
        return _create_placeholder_chart("暂无站点分类数据", figsize=figsize, dpi=dpi)

    color_map = {
        SITE_TYPE_PAID: "#3b82f6",
        SITE_TYPE_FREE: "#10b981",
        SITE_TYPE_SUBSCRIPTION: "#f59e0b",
    }

    type_keys = list(type_stats.keys())
    labels = [SITE_TYPE_LABELS.get(t, t) for t in type_keys]
    counts = [type_stats[t]["count"] for t in type_keys]
    balances = [type_stats[t]["balance"] for t in type_keys]
    colors = [color_map.get(t, "#94a3b8") for t in type_keys]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize, dpi=dpi)

    if sum(counts) > 0:
        wedges, texts, autotexts = ax1.pie(
            counts,
            labels=labels,
            colors=colors,
            startangle=90,
            autopct=lambda p: f"{p:.0f}%" if p >= 5 else "",
            pctdistance=0.72,
            labeldistance=1.07,
            wedgeprops={"width": 0.40, "edgecolor": "white", "linewidth": 1.2},
        )
        for txt in texts:
            txt.set_fontproperties(FONT_SMALL)
            txt.set_color("#334155")
        for txt in autotexts:
            txt.set_fontproperties(FONT_SMALL)
            txt.set_color("#0f172a")

        ax1.text(
            0,
            0,
            f"总计\n{sum(counts)}",
            ha="center",
            va="center",
            color="#0f172a",
            fontproperties=FONT_SUBTITLE,
        )
        ax1.set_title("站点类型占比", fontproperties=FONT_SUBTITLE, color="#0f172a", pad=6)
    else:
        ax1.text(0.5, 0.5, "无数据", ha="center", va="center", fontproperties=FONT_DEFAULT)
        ax1.axis("off")

    bars = ax2.bar(labels, balances, color=colors, width=0.58, edgecolor="white", linewidth=1.0)
    max_balance = max(balances) if balances else 0
    for bar, value in zip(bars, balances):
        ax2.text(
            bar.get_x() + bar.get_width() / 2,
            value + (max_balance * 0.03 if max_balance > 0 else 0.1),
            f"${value:,.0f}",
            ha="center",
            va="bottom",
            color="#1f2937",
            fontproperties=FONT_SMALL,
        )

    ax2.set_title("各类型余额对比", fontproperties=FONT_SUBTITLE, color="#0f172a", pad=6)
    ax2.set_ylabel("Balance (USD)", fontproperties=FONT_DEFAULT, color="#334155")
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"${y:,.0f}"))
    ax2.set_ylim(0, max_balance * 1.28 if max_balance > 0 else 1)

    _set_axis_style(ax2, grid_axis="y")
    _apply_tick_font(ax2)

    fig.tight_layout()
    return fig



def create_recharge_trend_chart(sites: list, months: int = 12, figsize=(6, 4), dpi=100) -> Figure:
    """Generate monthly recharge trend chart."""
    month_keys = _iter_recent_month_keys(months)
    month_totals = {key: 0.0 for key in month_keys}

    for site in sites:
        for record in site.get("recharge_records", []):
            amount = float(record.get("amount", 0) or 0)
            if amount <= 0:
                continue
            record_dt = _parse_datetime(record.get("date", ""))
            if not record_dt:
                continue
            month_key = record_dt.strftime("%Y-%m")
            if month_key in month_totals:
                month_totals[month_key] += amount

    values = [month_totals[key] for key in month_keys]
    labels = [datetime.strptime(key, "%Y-%m").strftime("%y-%m") for key in month_keys]

    if max(values, default=0) <= 0:
        return _create_placeholder_chart("暂无充值记录", figsize=figsize, dpi=dpi)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    ax.plot(labels, values, color="#2563eb", linewidth=2.2, marker="o", markersize=5.5)
    ax.fill_between(labels, values, color="#93c5fd", alpha=0.28)

    peak = max(values)
    for idx, value in enumerate(values):
        if value <= 0:
            continue
        ax.text(
            idx,
            value + peak * 0.03,
            f"${value:,.0f}",
            ha="center",
            va="bottom",
            color="#1f2937",
            fontproperties=FONT_SMALL,
        )

    ax.set_title("充值趋势（近12个月）", fontproperties=FONT_TITLE, color="#0f172a", pad=10)
    ax.set_xlabel("Month", fontproperties=FONT_DEFAULT, color="#334155")
    ax.set_ylabel("Amount (USD)", fontproperties=FONT_DEFAULT, color="#334155")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"${y:,.0f}"))
    ax.set_ylim(0, peak * 1.25)

    _set_axis_style(ax, grid_axis="y")
    _apply_tick_font(ax)

    step = max(1, len(labels) // 6)
    for idx, label in enumerate(ax.get_xticklabels()):
        label.set_visible(idx % step == 0 or idx == len(labels) - 1)

    fig.tight_layout()
    return fig



def create_checkin_activity_chart(logs=None, days: int = 30, figsize=(6, 4), dpi=100) -> Figure:
    """Generate recent check-in activity chart (success/failure + quota trend)."""
    if logs is None:
        logs = load_checkin_log()

    today = datetime.now().date()
    date_list = [today - timedelta(days=offset) for offset in range(max(days, 1) - 1, -1, -1)]
    date_keys = [d.strftime("%Y-%m-%d") for d in date_list]

    success_map = {key: 0 for key in date_keys}
    fail_map = {key: 0 for key in date_keys}
    quota_map = {key: 0.0 for key in date_keys}

    for log in logs:
        log_dt = _parse_datetime(log.get("time", ""))
        if not log_dt:
            continue
        key = log_dt.strftime("%Y-%m-%d")
        if key not in success_map:
            continue

        if log.get("success"):
            success_map[key] += 1
            quota_map[key] += float(log.get("quota_awarded", 0) or 0)
        else:
            fail_map[key] += 1

    success_values = [success_map[key] for key in date_keys]
    fail_values = [fail_map[key] for key in date_keys]
    quota_values = [quota_map[key] for key in date_keys]

    if max(success_values + fail_values, default=0) <= 0 and max(quota_values, default=0) <= 0:
        return _create_placeholder_chart("暂无签到记录", figsize=figsize, dpi=dpi)

    fig, ax1 = plt.subplots(figsize=figsize, dpi=dpi)
    x_positions = list(range(len(date_keys)))

    ax1.bar(
        x_positions,
        success_values,
        color="#10b981",
        width=0.72,
        label="成功",
        edgecolor="white",
        linewidth=0.8,
    )
    ax1.bar(
        x_positions,
        fail_values,
        bottom=success_values,
        color="#f97316",
        width=0.72,
        label="失败",
        edgecolor="white",
        linewidth=0.8,
    )

    ax2 = ax1.twinx()
    ax2.plot(
        x_positions,
        quota_values,
        color="#6366f1",
        marker="o",
        markersize=3.8,
        linewidth=2.0,
        label="额度(USD)",
    )

    display_labels = [datetime.strptime(key, "%Y-%m-%d").strftime("%m-%d") for key in date_keys]
    step = max(1, len(display_labels) // 7)
    tick_pos = [idx for idx in range(len(display_labels)) if (idx % step == 0 or idx == len(display_labels) - 1)]
    tick_labels = [display_labels[idx] for idx in tick_pos]
    ax1.set_xticks(tick_pos)
    ax1.set_xticklabels(tick_labels)

    ax1.set_title("签到活跃度（近30天）", fontproperties=FONT_TITLE, color="#0f172a", pad=10)
    ax1.set_ylabel("Check-in Count", fontproperties=FONT_DEFAULT, color="#334155")
    ax2.set_ylabel("Quota (USD)", fontproperties=FONT_DEFAULT, color="#334155")

    _set_axis_style(ax1, grid_axis="y")
    ax2.spines["top"].set_visible(False)
    ax2.spines["left"].set_visible(False)
    ax2.spines["right"].set_color("#cbd5e1")
    ax2.tick_params(colors="#334155", labelsize=9)

    ax2.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"${y:,.1f}"))

    _apply_tick_font(ax1)
    _apply_tick_font(ax2)

    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    legend = ax1.legend(handles1 + handles2, labels1 + labels2, loc="upper left", frameon=False, fontsize=8.8)
    for text_item in legend.get_texts():
        text_item.set_fontproperties(FONT_SMALL)

    peak_count = max([s + f for s, f in zip(success_values, fail_values)], default=0)
    ax1.set_ylim(0, peak_count * 1.28 if peak_count > 0 else 1)

    peak_quota = max(quota_values, default=0)
    ax2.set_ylim(0, peak_quota * 1.25 if peak_quota > 0 else 1)

    fig.tight_layout()
    return fig


def get_stats_summary(sites: list) -> dict:
    """
    获取统计摘要

    Returns:
        {
            "total_sites": 10,
            "total_balance_usd": 500.0,
            "total_recharge": 1000.0,
            "by_type": {
                "paid": {"count": 5, "balance": 300},
                "free": {"count": 3, "balance": 100},
                "subscription": {"count": 2, "balance": 100}
            }
        }
    """
    summary = {
        "total_sites": len(sites),
        "total_balance_usd": 0,
        "total_recharge": 0,
        "by_type": {}
    }

    for site in sites:
        site_type = site.get("type", SITE_TYPE_PAID)

        if site_type not in summary["by_type"]:
            summary["by_type"][site_type] = {"count": 0, "balance": 0}

        summary["by_type"][site_type]["count"] += 1

        # 统计余额（只计 USD/CNY）
        if site.get("balance_unit") in ("USD", "CNY", ""):
            balance = site.get("balance", 0)
            summary["by_type"][site_type]["balance"] += balance
            summary["total_balance_usd"] += balance

        # 统计充值总额
        for record in site.get("recharge_records", []):
            summary["total_recharge"] += record.get("amount", 0)

    return summary
