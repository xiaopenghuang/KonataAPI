"""
统计模块 - 站点档案管理与图表生成
"""
import json
import os
import uuid
import warnings
from datetime import datetime
from typing import Optional

# 过滤 matplotlib 字体警告
warnings.filterwarnings('ignore', message='Glyph .* missing from')

import matplotlib
matplotlib.use('Agg')  # 非交互式后端，避免 tkinter 冲突
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

# 设置中文字体（在导入后立即设置）
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'STSong', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

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

def create_balance_bar_chart(sites: list, figsize=(6, 4), dpi=100) -> Figure:
    """
    生成余额柱状图

    Args:
        sites: 站点列表
        figsize: 图表尺寸
        dpi: 分辨率

    Returns:
        matplotlib Figure 对象
    """
    # 过滤有余额的站点，按余额排序
    valid_sites = [s for s in sites if s.get("balance", 0) > 0 and s.get("balance_unit") in ("USD", "CNY", "")]
    valid_sites = sorted(valid_sites, key=lambda x: x.get("balance", 0), reverse=True)[:10]  # 最多显示10个

    if not valid_sites:
        # 无数据时返回空图
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        ax.text(0.5, 0.5, "暂无余额数据", ha='center', va='center', fontsize=12, color='gray')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        plt.tight_layout()
        return fig

    names = [s["name"][:8] for s in valid_sites]  # 名称截断
    balances = [s["balance"] for s in valid_sites]

    # 根据站点类型设置颜色
    colors = []
    for s in valid_sites:
        site_type = s.get("type", SITE_TYPE_PAID)
        if site_type == SITE_TYPE_FREE:
            colors.append("#4CAF50")  # 绿色 - 公益站
        elif site_type == SITE_TYPE_SUBSCRIPTION:
            colors.append("#FF9800")  # 橙色 - 订阅转API
        else:
            colors.append("#2196F3")  # 蓝色 - 付费站

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    bars = ax.barh(names, balances, color=colors, edgecolor='white', height=0.6)

    # 在柱子上显示数值
    for bar, balance in zip(bars, balances):
        width = bar.get_width()
        ax.text(width + max(balances) * 0.02, bar.get_y() + bar.get_height()/2,
                f'${balance:.2f}', va='center', fontsize=9)

    ax.set_xlabel('余额 (USD)', fontsize=10)
    ax.set_title('各站点余额', fontsize=12, fontweight='bold')
    ax.invert_yaxis()  # 最大的在上面
    ax.set_xlim(0, max(balances) * 1.2)

    plt.tight_layout()
    return fig


def create_type_stats_chart(sites: list, figsize=(5, 4), dpi=100) -> Figure:
    """
    生成分类统计图（按站点类型分组）

    Args:
        sites: 站点列表
        figsize: 图表尺寸
        dpi: 分辨率

    Returns:
        matplotlib Figure 对象
    """
    # 按类型统计
    type_stats = {}
    for site in sites:
        site_type = site.get("type", SITE_TYPE_PAID)
        if site_type not in type_stats:
            type_stats[site_type] = {"count": 0, "balance": 0}
        type_stats[site_type]["count"] += 1
        # 只统计 USD/CNY 余额
        if site.get("balance_unit") in ("USD", "CNY", ""):
            type_stats[site_type]["balance"] += site.get("balance", 0)

    if not type_stats:
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        ax.text(0.5, 0.5, "暂无站点数据", ha='center', va='center', fontsize=12, color='gray')
        ax.axis('off')
        plt.tight_layout()
        return fig

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize, dpi=dpi)

    # 颜色映射
    color_map = {
        SITE_TYPE_PAID: "#2196F3",
        SITE_TYPE_FREE: "#4CAF50",
        SITE_TYPE_SUBSCRIPTION: "#FF9800",
    }

    labels = [SITE_TYPE_LABELS.get(t, t) for t in type_stats.keys()]
    counts = [type_stats[t]["count"] for t in type_stats.keys()]
    balances = [type_stats[t]["balance"] for t in type_stats.keys()]
    colors = [color_map.get(t, "#9E9E9E") for t in type_stats.keys()]

    # 左图：站点数量饼图
    if sum(counts) > 0:
        wedges, texts, autotexts = ax1.pie(
            counts, labels=labels, colors=colors,
            autopct=lambda p: f'{int(p*sum(counts)/100)}个' if p > 0 else '',
            startangle=90, textprops={'fontsize': 9}
        )
        ax1.set_title('站点数量', fontsize=11, fontweight='bold')
    else:
        ax1.text(0.5, 0.5, "无数据", ha='center', va='center')
        ax1.axis('off')

    # 右图：余额分布饼图
    if sum(balances) > 0:
        wedges, texts, autotexts = ax2.pie(
            balances, labels=labels, colors=colors,
            autopct=lambda p: f'${p*sum(balances)/100:.0f}' if p > 5 else '',
            startangle=90, textprops={'fontsize': 9}
        )
        ax2.set_title('余额分布', fontsize=11, fontweight='bold')
    else:
        ax2.text(0.5, 0.5, "无余额数据", ha='center', va='center', fontsize=10, color='gray')
        ax2.axis('off')

    plt.tight_layout()
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
