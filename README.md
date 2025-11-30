# 股票实时交易数据获取客户端模块

## 简介

这是一个股票实时交易数据获取客户端模块，通过 WebSocket 连接到服务器，接收执行请求后从 Infoway API 批量获取股票实时交易数据并保存到 MongoDB 数据库。

## 功能特性

- **WebSocket 客户端连接**：与服务器建立 WebSocket 连接，接收执行命令
- **股票实时数据采集**：从 Infoway API 批量获取指定股票的实时交易数据
- **数据存储**：将股票实时交易数据保存到 MongoDB 数据库
- **批量处理**：支持批量处理多个股票代码，一次请求获取多个股票数据
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
- `MONGODB_REALTIME_COLLECTION_NAME` - 实时数据集合名称（可选，默认 `realtime`，可通过 `MONGODB_COLLECTION_NAME` 兼容老配置）
- `MONGODB_CLOSE_COLLECTION_NAME` - 收盘快照集合名称（可选，默认 `close`）
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
# 指定股票代码列表（支持批量获取）
python run_main.py --codes TSLA.US AAPL.US USDCNY
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
2. **API 调用**：调用 Infoway API 批量获取指定股票的实时交易数据
3. **数据存储**：将股票实时交易数据保存到 MongoDB

### API接口说明

**接口地址**：`https://data.infoway.io/stock/batch_trade/{codes}`

**请求方式**：GET

**请求头**：
- `apiKey` - Infoway API密钥（必需）

**请求参数**：
- `codes` - 股票代码列表，多个代码用逗号分隔（如：`TSLA.US,AAPL.US`）

**返回格式**：
```json
{
  "ret": 200,
  "msg": "success",
  "traceId": "...",
  "data": [
    {
      "s": "TSLA.US",
      "t": 1750177346523,
      "p": "5188.211",
      "v": "3.0",
      "vw": "15564.6330",
      "td": 0
    }
  ]
}
```

### 数据字段

保存到 MongoDB 的股票实时交易数据包含以下字段：
- `s` - 标的名称（如：TSLA.US）
- `t` - 交易时间（时间戳）
- `p` - 价格
- `v` - 成交量
- `vw` - 成交额
- `td` - 交易方向（0为默认值，1为Buy，2为SELL）
- `stock_code` - 股票代码（自动添加）
- `create_time` - 数据创建时间（自动添加）

### 性能优化

- **连接复用**：MongoDB 连接和集合对象全局复用，避免重复创建连接
- **批量获取**：支持一次请求获取多个股票数据，提高效率

## 注意事项

- 确保服务器地址和端口配置正确
- 首次运行前必须先执行模块注册
- 模块通过 WebSocket 连接服务器，需要网络畅通
- 确保 MongoDB 连接字符串配置正确，支持 `mongodb://` 和 `mongodb+srv://` 格式
- 确保 `INFOWAY_API_KEY` 环境变量已正确配置
- 日志文件保存在 `logs/` 目录下
- 股票代码格式：如 `TSLA.US`、`AAPL.US`、`USDCNY` 等（支持国际股票代码和货币对）
- API支持批量获取，多个股票代码用逗号分隔
