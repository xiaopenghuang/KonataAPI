# KonataAPI - 此方API查查

一个用于查询 AI 中转站余额和调用日志的桌面工具。

## 功能特性

- 支持多中转站配置管理
- 查询账户余额（USD / Token 两种统计方式）
- 查询调用日志
- 批量查询所有配置的余额
- 自定义 API 接口路径
- 按站点配置日志代理（解决部分站点限制）
- 查看原始 API 返回数据
- **系统托盘支持** - 最小化到托盘，右键菜单快捷操作
- **开机自启动** - 可选随 Windows 启动自动运行
- **自动批量查询** - 定时自动查询所有站点余额

![alt text](assets/image.png)
![alt text](assets/image-1.png)
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

部分中转站的日志接口有访问限制，需要通过代理访问。在站点配置中填写「日志代理」地址即可：

```
https://proxy.cifang.xyz/proxy
```

留空则直接访问。

### 配置文件格式

配置文件位于 `config/config.json`，格式如下：

```json
{
  "profiles": [
    {
      "name": "站点名称",
      "url": "https://api.example.com",
      "key": "sk-your-api-key",
      "proxy": "https://proxy.example.com/proxy"
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
  - `key` - API Key
  - `proxy` - 日志代理地址（可选，留空则直接访问）
- `api_endpoints` - 全局接口路径配置（可在设置中修改）
- `minimize_to_tray` - 关闭窗口时是否最小化到托盘
- `auto_query` - 自动查询设置
  - `enabled` - 是否启用自动查询
  - `interval_minutes` - 查询间隔（分钟）

## 打包为可执行文件

### 方式一：使用打包脚本（推荐）

1. 编辑 `build.bat`，填写你的 Conda 路径和环境：
   ```bat
   set CONDA_PATH=
   set CONDA_ENV=
   ```

2. 双击运行 `build.bat`

3. 打包完成后，可执行文件位于 `dist/KonataAPI.exe`

### 方式二：手动打包

```bash
pip install pyinstaller

pyinstaller --onefile --windowed --name "KonataAPI" ^
    --icon=assets/icon.ico ^
    --add-data "assets;assets" ^
    --add-data "config;config" ^
    --add-data "src/konata_api;konata_api" ^
    --hidden-import=ttkbootstrap ^
    --hidden-import=ttkbootstrap.themes ^
    --hidden-import=ttkbootstrap.style ^
    --hidden-import=ttkbootstrap.widgets ^
    --hidden-import=ttkbootstrap.widgets.scrolled ^
    --hidden-import=ttkbootstrap.constants ^
    --hidden-import=ttkbootstrap.window ^
    --collect-submodules=ttkbootstrap ^
    --hidden-import=PIL ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=PIL.Image ^
    --hidden-import=PIL.ImageTk ^
    --hidden-import=requests ^
    main.py
```

## 项目结构

```
KonataAPI/
├── main.py                     # 入口文件
├── build.bat                   # 打包脚本
├── src/
│   └── konata_api/
│       ├── __init__.py
│       ├── app.py              # GUI 主应用
│       ├── dialogs.py          # 对话框组件
│       ├── tray.py             # 系统托盘模块
│       ├── utils.py            # 工具函数
│       └── api.py              # API 查询逻辑
├── assets/
│   ├── icon.ico                # 程序图标
│   └── background.jpg          # 背景图片
├── config/
│   └── config.example.json     # 配置文件示例
├── requirements.txt
├── README.md
└── .gitignore
```

## License

MIT
