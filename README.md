# 天气爬虫客户端模块

## 简介

这是一个天气数据爬虫客户端模块，通过 WebSocket 连接到服务器，接收执行请求后从 MSN 天气 API 获取天气数据并保存到 MongoDB 数据库。

## 功能特性

- **WebSocket 客户端连接**：与服务器建立 WebSocket 连接，接收执行命令
- **天气数据采集**：从 MSN 天气 API 获取指定城市的天气预报数据
- **数据存储**：将天气数据保存到 MongoDB 数据库，支持自动去重
- **批量处理**：支持批量处理多个城市，使用线程池并发处理提高效率
- **城市坐标映射**：内置中国主要城市坐标映射，支持城市名称到经纬度转换
- **整点数据过滤**：自动过滤非整点数据，只保存整点天气数据
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

#### 方式二：直接使用 Python

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
- `MONGODB_DB_NAME` - MongoDB 数据库名称
- `MONGODB_COLLECTION_NAME` - MongoDB 集合名称
- `WEATHER_API_KEY` - MSN 天气 API 密钥（可选，有默认值）
- `WEATHER_APP_ID` - MSN 天气应用 ID（可选，有默认值）
- `WEATHER_DAYS` - 获取未来天数（可选，默认 10 天）
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
# 使用默认城市列表（北京,上海,广州,深圳）和默认天数（10天）
python run_main.py

# 指定城市列表和天数
python run_main.py "北京,上海,广州,深圳" 10

# 使用环境变量
export CITY_LIST="武汉,宜昌,孝感"
export DAYS=7
python run_main.py
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
│   ├── main.py              # 主业务逻辑（天气数据采集和存储）
│   └── city_coordinates.py  # 城市坐标映射工具
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

1. **接收请求**：通过 WebSocket 接收服务器发送的执行请求，包含城市列表和天数参数
2. **坐标转换**：根据城市名称查询对应的经纬度坐标（使用内置城市坐标映射）
3. **API 调用**：调用 MSN 天气 API 获取指定坐标的天气预报数据
4. **数据过滤**：自动过滤非整点数据，只保留整点（小时）天气数据
5. **数据存储**：将天气数据保存到 MongoDB，自动去重（基于城市和时间）

### 数据字段

保存到 MongoDB 的天气数据包含以下字段：
- `city` - 城市名称
- `time` - 时间（ISO 格式）
- `temp` - 温度
- `utci` - 体感温度
- `baro` - 气压
- `dewPt` - 露点
- `vis` - 能见度
- `windSpd` - 风速
- `windDir` - 风向
- `cloudCover` - 云层厚度
- `cap` - 天气类型（文字描述）
- `created_at` - 数据创建时间

### 性能优化

- **连接复用**：MongoDB 连接和集合对象全局复用，避免重复创建连接
- **批量查询**：使用批量查询检查数据是否已存在，减少数据库查询次数
- **并发处理**：使用线程池并发处理多个城市，最多 5 个并发
- **索引优化**：在 MongoDB 中创建 `(city, time)` 复合唯一索引，提高查询和去重效率

## 注意事项

- 确保服务器地址和端口配置正确
- 首次运行前必须先执行模块注册
- 模块通过 WebSocket 连接服务器，需要网络畅通
- 确保 MongoDB 连接字符串配置正确，支持 `mongodb://` 和 `mongodb+srv://` 格式
- 日志文件保存在 `logs/` 目录下
- 城市坐标映射目前仅支持内置的城市列表，如需添加新城市，请编辑 `main/city_coordinates.py`
- 数据去重基于 `(city, time)` 复合唯一索引，相同城市和时间的记录不会重复插入

