"""工具函数模块"""

import json
import os
import sys
import winreg


def get_exe_dir():
    """获取可执行文件所在目录（打包后用于保存配置）"""
    if hasattr(sys, '_MEIPASS'):
        # 打包后：返回 exe 所在目录
        return os.path.dirname(sys.executable)
    # 开发时：返回项目根目录
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_resource_dir():
    """获取资源文件目录（打包后的临时目录）"""
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resource_path(relative_path):
    """获取资源文件的绝对路径（图标、背景图等只读资源）"""
    return os.path.join(get_resource_dir(), relative_path)


def get_config_path():
    """获取配置文件路径（可写）"""
    return os.path.join(get_exe_dir(), "config", "config.json")


def get_data_dir():
    """获取数据目录（可写，用于保存结果等）"""
    return get_exe_dir()


def load_config():
    """加载配置文件"""
    config_file = get_config_path()
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"profiles": []}


def save_config(config):
    """保存配置文件"""
    config_file = get_config_path()
    # 确保 config 目录存在
    config_dir = os.path.dirname(config_file)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# === 开机自启动相关 ===
APP_NAME = "KonataAPI"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def get_exe_path():
    """获取当前可执行文件路径"""
    if hasattr(sys, '_MEIPASS'):
        # 打包后：返回 exe 路径
        return sys.executable
    # 开发时：返回 python 解释器 + main.py
    main_py = os.path.join(get_exe_dir(), "main.py")
    return f'"{sys.executable}" "{main_py}"'


def is_autostart_enabled():
    """检查是否已设置开机自启动"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        try:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False


def set_autostart(enable: bool):
    """设置或取消开机自启动"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        if enable:
            exe_path = get_exe_path()
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass  # 本来就没有，不需要删除
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"设置开机自启动失败: {e}")
        return False
