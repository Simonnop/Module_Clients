# 股票实时交易数据获取客户端模块

## 简介

这是一个股票实时交易数据获取客户端模块，通过 WebSocket 连接到服务器，接收执行请求后从必盈API获取股票实时交易数据并保存到 MongoDB 数据库。

## 功能特性

- **WebSocket 客户端连接**：与服务器建立 WebSocket 连接，接收执行命令
- **股票实时数据采集**：从必盈API获取指定股票的实时交易数据（日线最新数据）
- **数据存储**：将股票实时交易数据保存到 MongoDB 数据库
- **批量处理**：支持批量处理多个股票代码
- **License管理**：自动管理License使用，支持多License轮询和配额管理
- **心跳机制**：保持 WebSocket 连接活跃
- **直接运行模式**：支持不通过服务器直接运行，方便本地测试

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用说明

### 1. 模块注册

首次使用前，需要先注册模块：

#### 方式一：使用注册脚本（推荐）

```bash
chmod +x register.sh
./register.sh
```

#### 方式二：使用管理脚本

```bash
./manage.sh register
```

#### 方式三：直接使用 Python

```bash
python connect/register.py
```

注册成功后会在 `config/module_hash.txt` 文件中保存模块哈希值。

### 2. 配置环境变量

安全性相关的配置（如服务器地址等）需要配置在 `.env` 文件中：

```bash
# 复制示例配置文件（如果存在）
cp config/.env.example config/.env

# 编辑 .env 文件，填入实际配置值
# 注意：.env 文件包含敏感信息，不会被提交到版本控制
```

`.env` 文件中需要配置的项：
- `SERVER_IP` - 服务器 IP 地址
- `SERVER_PORT` - 服务器端口
- `MONGODB_HOST` - MongoDB 连接字符串（完整连接字符串，如 `mongodb+srv://...` 或 `mongodb://...`）
- `MONGODB_DB_NAME` - MongoDB 数据库名称（可选，默认 `forecast_platform`）
- `MONGODB_COLLECTION_NAME` - MongoDB 集合名称（可选，默认 `stock_data`）
- `BIYING_API_BASE_URL` - 必盈API基础URL（可选，默认 `https://api.biyingapi.com/hsstock/real/time`）
- `HEARTBEAT_INTERVAL` - 心跳间隔秒数（可选，默认 10 秒）

### 3. 启动模块

#### 方式一：使用管理脚本（推荐）

```bash
# 启动模块（后台运行）
./manage.sh start

# 查看运行状态
./manage.sh status

# 查看日志
./manage.sh logs

# 实时查看日志
./manage.sh logs-follow

# 停止模块
./manage.sh stop

# 重启模块
./manage.sh restart
```

#### 方式二：使用启动脚本

```bash
chmod +x run.sh
./run.sh
```

#### 方式三：直接使用 Python

```bash
python connect/client_connect.py
```

#### 方式四：直接运行主函数（本地测试）

不通过服务器，直接运行主函数进行测试：

```bash
# 指定股票代码列表
python run_main.py --codes 000001 000002 600000

# 查看License使用状态
python run_main.py --status

# 初始化License统计
python run_main.py --init
```

### 4. 管理脚本命令

管理脚本 `manage.sh` 提供以下命令：

- `start` - 启动模块（后台运行）
- `stop` - 停止模块
- `restart` - 重启模块
- `status` - 查看运行状态
- `logs [N]` - 查看日志（默认最后50行）
- `logs-follow` - 实时查看日志
- `install` - 安装依赖包
- `register` - 注册模块
- `help` - 显示帮助信息

## 目录结构

```
Module_Clients/
├── connect/              # 连接相关模块
│   ├── client_connect.py    # WebSocket 客户端
│   ├── model_router.py      # 请求路由处理
│   └── register.py          # 模块注册
├── main/                 # 业务执行模块
│   ├── main.py              # 主业务逻辑（股票实时交易数据采集和存储）
│   └── license_manager.py  # License管理模块
├── config/               # 配置文件目录
│   ├── config.py            # 配置文件
│   ├── .env.example         # 环境变量配置示例
│   └── module_hash.txt      # 模块哈希值
├── logs/                # 日志目录
├── run.sh               # 启动脚本
├── register.sh          # 模块注册脚本
├── run_main.py          # 直接运行主函数脚本（本地测试）
├── manage.sh            # 管理脚本
├── requirements.txt     # 依赖包列表
└── README.md           # 说明文档
```

## 业务逻辑说明

### 数据采集流程

1. **接收请求**：通过 WebSocket 接收服务器发送的执行请求，包含股票代码列表参数
2. **License管理**：自动获取可用License，支持多License轮询和配额管理
3. **API 调用**：调用必盈API获取指定股票的实时交易数据
4. **数据存储**：将股票实时交易数据保存到 MongoDB

### API接口说明

**接口地址**：`https://api.biyingapi.com/hsstock/real/time/{股票代码}/{License密钥}`

**请求频率限制**：
- 普通版：1分钟300次
- 包年版：1分钟3000次
- 白金版：1分钟6000次

**返回格式**：标准JSON格式 `[{},...{}]`

### 数据字段

保存到 MongoDB 的股票实时交易数据包含以下字段：
- `p` - 最新价
- `o` - 开盘价
- `h` - 最高价
- `l` - 最低价
- `yc` - 前收盘价
- `cje` - 成交总额
- `v` - 成交总量
- `pv` - 原始成交总量
- `t` - 更新时间
- `ud` - 涨跌额
- `pc` - 涨跌幅
- `zf` - 振幅
- `pe` - 市盈率
- `tr` - 换手率
- `pb_ratio` - 市净率
- `tv` - 成交量
- `stock_code` - 股票代码（自动添加）
- `create_time` - 数据创建时间（自动添加）

### 性能优化

- **连接复用**：MongoDB 连接和集合对象全局复用，避免重复创建连接
- **License管理**：自动管理License使用，支持多License轮询，避免单个License配额耗尽
- **请求频率控制**：自动控制请求频率，避免超过API限制（默认0.2秒间隔，对应1分钟300次）

## 注意事项

- 确保服务器地址和端口配置正确
- 首次运行前必须先执行模块注册
- 模块通过 WebSocket 连接服务器，需要网络畅通
- 确保 MongoDB 连接字符串配置正确，支持 `mongodb://` 和 `mongodb+srv://` 格式
- 日志文件保存在 `logs/` 目录下
- 股票代码格式：如 `000001`（深市）、`600000`（沪市）等
- API返回数据格式为数组，代码会自动取第一个元素
- 请求频率限制为1分钟300次（普通版），代码中已设置0.2秒延迟以确保不超过限制
