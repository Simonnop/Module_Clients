# Tester 模块

## 简介

这是一个用于测试的模块，通过 WebSocket 连接到服务器，接收并处理执行请求。

## 功能特性

- WebSocket 客户端连接
- 接收服务器执行命令
- 处理业务逻辑并返回结果
- 心跳机制保持连接活跃

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用说明

### 1. 模块注册

首次使用前，需要先注册模块：

```bash
python connect/register.py
```

注册成功后会在 `res/module_hash.txt` 文件中保存模块哈希值。

### 2. 配置环境变量

安全性相关的配置（如服务器地址等）需要配置在 `.env` 文件中：

```bash
# 复制示例配置文件
cp res/.env.example res/.env

# 编辑 .env 文件，填入实际配置值
# 注意：.env 文件包含敏感信息，不会被提交到版本控制
```

`.env` 文件中需要配置的项：
- `SERVER_IP` - 服务器 IP 地址
- `SERVER_PORT` - 服务器端口

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
tester/
├── connect/              # 连接相关模块
│   ├── client_connect.py    # WebSocket 客户端
│   ├── model_router.py      # 请求路由处理
│   └── register.py          # 模块注册
├── execute/             # 业务执行模块
│   └── main.py              # 主业务逻辑
├── res/                 # 资源文件
│   ├── config.py            # 配置文件
│   └── module_hash.txt      # 模块哈希值
├── logs/                # 日志目录
├── run.sh               # 启动脚本
├── manage.sh            # 管理脚本
├── requirements.txt     # 依赖包列表
└── README.md           # 说明文档
```

## 注意事项

- 确保服务器地址和端口配置正确
- 首次运行前必须先执行模块注册
- 模块通过 WebSocket 连接服务器，需要网络畅通
- 日志文件保存在 `logs/` 目录下

