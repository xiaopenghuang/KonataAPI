# KonataAPI - 此方API查查

一个用于查询 AI 中转站余额和调用日志的桌面工具。

## 功能特性

- 支持多中转站配置管理
- 查询账户余额（USD / Token 两种统计方式）
- 查询调用日志
- 批量查询所有配置的余额
- 自定义 API 接口路径
- **独立认证配置** - 余额查询和日志查询可分别配置认证方式
- **多种认证方式** - 支持 Bearer Token 和 URL Key 两种认证
- **多种 API 格式** - 自动检测 OpenAI、NewAPI、sub2api 等多种格式
- **站点级别配置** - 每个站点可独立配置认证方式和接口路径
- 按站点配置日志代理（解决部分站点限制）
- 查看原始 API 返回数据
- **系统托盘支持** - 最小化到托盘，右键菜单快捷操作
- **开机自启动** - 可选随 Windows 启动自动运行
- **自动批量查询** - 定时自动查询所有站点余额
- **站点统计模块** - 管理站点档案、手动记录余额、记录充值、统计消费
- **站点测试模块** - 连通性测试、Claude 真伪性检测、原生对话
  - **多种 API 预设** - 支持原生 Anthropic/OpenAI、中转站格式、Claude CLI 真实格式
  - **Claude CLI 真实格式** - 完全模拟 Claude Code CLI 请求，可绕过部分中转站验证



## 支持的 API 格式

KonataAPI 支持自动检测多种中转站 API 格式：

| 格式 | 余额接口 | 日志接口 | 认证方式 | 说明 |
|------|---------|---------|---------|------|
| **OpenAI 兼容** | `/v1/dashboard/billing/subscription` | - | Bearer sk-xxx | 大部分中转站默认格式 |
| **NewAPI / One-API** | `/api/usage/token/` | `/api/log/token` | Bearer sk-xxx | 国内常见中转站 |
| **sub2api** | `/v1/usage` | ❌ 不支持 | Bearer sk-xxx | Claude 订阅转 API |

### 自动检测顺序

程序会按以下顺序自动尝试不同的 API 格式：

1. **OpenAI 兼容格式** - `/v1/dashboard/billing/subscription`
2. **sub2api 格式** - `/v1/usage`（返回余额+用量统计）
3. **JWT Token 格式** - `/api/v1/auth/me`（需要登录态）
4. **NewAPI Token 格式** - `/api/usage/token/`

大多数情况下无需手动配置，程序会自动识别站点类型。

### sub2api 站点说明

基于 [sub2api](https://github.com/Wei-Shaw/sub2api) 的站点（如 Forward）：
- ✅ **余额查询**：支持，通过 `/v1/usage` 接口
- ❌ **日志查询**：不支持，sub2api 的日志接口需要 JWT Token（登录态）

## 安装

### 依赖

- Python 3.8+
- Windows（GUI 基于 tkinter）

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/your-username/KonataAPI.git
cd KonataAPI

# 安装依赖
pip install -r requirements.txt
```

## 使用方法

### 运行程序

```bash
python main.py
```

### 配置站点

1. 填写配置名称、Base URL、API Key
2. 点击「保存配置」
3. 双击左侧列表可快速加载已保存的配置

### 日志代理（可选）

部分中转站的日志接口有访问限制，需要通过代理访问。在站点配置中填写「日志代理」地址即可，留空则直接访问。

### 配置文件格式

配置文件位于 `config/config.json`，格式如下：

```json
{
  "profiles": [
    {
      "name": "站点名称",
      "url": "https://api.example.com",
      "key": "sk-your-api-key",
      "proxy": "https://proxy.example.com/proxy",
      "balance_auth_type": "bearer",
      "log_auth_type": "url_key",
      "endpoints": {
        "balance_subscription": "/v1/dashboard/billing/subscription",
        "balance_usage": "/v1/dashboard/billing/usage",
        "logs": "/api/log/token"
      }
    }
  ],
  "api_endpoints": {
    "balance_subscription": "/v1/dashboard/billing/subscription",
    "balance_usage": "/v1/dashboard/billing/usage",
    "logs": "/api/log/token",
    "logs_page_size": 50
  },
  "minimize_to_tray": true,
  "auto_query": {
    "enabled": false,
    "interval_minutes": 30
  }
}
```

字段说明：
- `profiles` - 站点配置列表
  - `name` - 站点名称
  - `url` - API 基础地址
  - `key` - API Key 或 JWT Token
  - `proxy` - 日志代理地址（可选，留空则直接访问）
  - `balance_auth_type` - 余额查询认证方式（可选）
    - `"bearer"` - 使用 Authorization Header 认证（默认）
    - `"url_key"` - 使用 URL 参数 `?key=xxx` 认证
  - `log_auth_type` - 日志查询认证方式（可选）
    - `"bearer"` - 使用 Authorization Header 认证
    - `"url_key"` - 使用 URL 参数 `?key=xxx` 认证（默认）
  - `endpoints` - 站点级别自定义接口路径（可选，覆盖全局设置）
- `api_endpoints` - 全局接口路径配置（可在设置中修改）
- `minimize_to_tray` - 关闭窗口时是否最小化到托盘
- `auto_query` - 自动查询设置
  - `enabled` - 是否启用自动查询
  - `interval_minutes` - 查询间隔（分钟）

## 打包为可执行文件

### 方式一：使用 spec 文件（推荐）

```bash
pip install pyinstaller
pyinstaller KonataAPI.spec --clean
```

### 方式二：使用打包脚本

1. 编辑 `build.bat`，填写你的 Conda 路径和环境：
   ```bat
   set CONDA_PATH=
   set CONDA_ENV=
   ```

2. 双击运行 `build.bat`

3. 打包完成后，可执行文件位于 `dist/KonataAPI.exe`

## 项目结构

```
KonataAPI/
├── main.py                     # 入口文件
├── build.bat                   # 打包脚本
├── KonataAPI.spec              # PyInstaller 打包配置
├── src/
│   └── konata_api/
│       ├── __init__.py
│       ├── app.py              # GUI 主应用
│       ├── dialogs.py          # 对话框组件
│       ├── tray.py             # 系统托盘模块
│       ├── utils.py            # 工具函数
│       ├── api.py              # API 查询逻辑
│       ├── api_presets.py      # API 接口预设配置
│       ├── stats.py            # 站点统计数据管理
│       ├── stats_dialog.py     # 站点统计对话框
│       ├── conversation_test.py # Claude 真伪检测核心
│       ├── test_dialog.py      # 站点测试对话框
│       └── test_settings_dialog.py # 测试设置对话框
├── assets/
│   ├── icon.ico                # 程序图标
│   └── background.jpg          # 背景图片
├── config/
│   ├── config.example.json     # 配置文件示例
│   ├── cli_tools.json          # Claude CLI 工具定义（模型检测用）
│   ├── cli_system.json         # Claude CLI System Prompt（模型检测用）
│   └── stats.json              # 站点统计数据（自动生成）
├── requirements.txt
├── README.md
└── .gitignore
```

## License

MIT
