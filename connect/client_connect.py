"""
WebSocket客户端连接
"""
import threading
import time
import logging
import json
import os
import sys
import websocket  # 使用 websocket-client 库

# 确保项目根路径在 sys.path 中，便于绝对导入
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 将当前目录添加到 sys.path，以便导入同目录下的模块
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 使用绝对导入，避免相对导入问题
try:
    from model_router import process_request
except ImportError:
    # 如果直接导入失败，尝试使用 importlib
    import importlib.util
    model_router_path = os.path.join(current_dir, 'model_router.py')
    spec = importlib.util.spec_from_file_location("model_router", model_router_path)
    model_router = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model_router)
    process_request = model_router.process_request

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    """
    加载配置文件
    
    Returns:
        配置模块，如果加载失败则返回None
    """
    try:
        import importlib.util
        config_path = os.path.join(os.path.dirname(__file__), '../config/config.py')
        spec = importlib.util.spec_from_file_location("config", config_path)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        return config_module
    except Exception as e:
        logger.error(f"加载配置时发生错误: {e}")
        return None

# 加载配置并获取心跳间隔
config_module = load_config()
if not config_module:
    raise ValueError("无法加载配置文件")

HEARTBEAT_INTERVAL = getattr(config_module, 'HEARTBEAT_INTERVAL')
if HEARTBEAT_INTERVAL is None:
    raise ValueError("配置文件中缺少 HEARTBEAT_INTERVAL")

def read_module_hash():
    """
    读取模块哈希值
    
    Returns:
        模块哈希值，如果读取失败则返回None
    """
    try:
        # 使用相对路径读取 hash 文件
        hash_file_path = os.path.join(os.path.dirname(__file__), '../config/module_hash.txt')
        with open(hash_file_path, 'r') as f:
            hash_value = f.read().strip()
        return hash_value
    except FileNotFoundError:
        logger.error("错误：找不到 module_hash.txt 文件，请先运行 register.py 进行模块注册")
        return None
    except Exception as e:
        logger.error(f"读取 hash 值时发生错误: {e}")
        return None

class WebSocketClient:
    """
    WebSocket客户端类
    管理与服务器的WebSocket连接
    """
    
    def __init__(self, url, module_hash):
        """
        初始化WebSocket客户端
        
        Args:
            url: WebSocket服务器URL
            module_hash: 模块哈希值
        """
        # 确保 URL 格式正确，添加命名空间
        if '/websocket' in url and not url.endswith('/websocket'):
            base_url = url
        elif url.endswith('/websocket'):
            base_url = url
        else:
            base_url = f"{url}/websocket"
            
        self.url = f"{base_url}?hash={module_hash}"
        logger.info(f"连接到 WebSocket URL: {self.url}")
        self.ws = None
        self.is_connected = False
        self.heartbeat_thread = None
        self.should_reconnect = True  # 是否应该重连
        self.reconnecting = False  # 是否正在重连中
    
    def on_message(self, ws, message):
        """
        消息处理回调
        
        Args:
            ws: WebSocket连接
            message: 接收到的消息
        """
        # 处理简单文本消息
        if message == "receive result":
            logger.info("收到处理结果确认")
            return
        elif message == "heartbeat confirm":
            logger.debug("收到心跳确认")
            return
        
        # 解析 JSON 消息
        try:
            parsed_message = json.loads(message)
            message_data = parsed_message.get('message')
            
            # 如果 message_data 是字符串，尝试解析
            if isinstance(message_data, str):
                try:
                    message_data = json.loads(message_data)
                except json.JSONDecodeError:
                    logger.warning(f"无法解析 message 字段中的 JSON: {message_data}")
                    return
            
            # 检查消息类型
            if not isinstance(message_data, dict):
                logger.warning(f"消息格式无效，期望字典类型: {type(message_data)}")
                return
            
            message_type = message_data.get('type')
            
            # 处理 shutdown 命令
            if message_type == 'shutdown':
                logger.info("收到 shutdown 命令，准备关闭模块")
                # 发送确认消息
                try:
                    self.ws.send(json.dumps({
                        'status': 'success',
                        'message': '模块正在关闭'
                    }))
                except Exception as e:
                    logger.error(f"发送 shutdown 确认消息失败: {e}")
                
                # 关闭连接
                self.close()
                # 退出程序
                import os
                os._exit(0)
                return
            
            # 处理 execute 命令
            elif message_type == 'execute':
                logger.info("收到执行命令")
                logger.debug(f"消息内容: {json.dumps(message_data, ensure_ascii=False, indent=2)}")
                
                # 调用 process_request 处理执行请求
                try:
                    result = process_request(message)
                    # 发送处理结果
                    self.ws.send(json.dumps(result))
                    logger.info("执行完成，结果已发送")
                except Exception as e:
                    logger.exception(f"处理执行请求时发生异常: {e}")
                    # 发送错误响应
                    error_response = {
                        'status': 'error',
                        'message': f'处理请求时发生异常: {str(e)}'
                    }
                    try:
                        self.ws.send(json.dumps(error_response))
                    except Exception as send_error:
                        logger.error(f"发送错误响应失败: {send_error}")
                return
            
            # 未知消息类型
            else:
                logger.warning(f"未知的消息类型: {message_type}")
                logger.debug(f"完整消息: {json.dumps(message_data, ensure_ascii=False, indent=2)}")
                return
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            logger.debug(f"原始消息: {message}")
            return
        except Exception as e:
            logger.exception(f"处理消息时发生未预期的异常: {e}")
            logger.debug(f"原始消息: {message}")
            return
        
    
    def on_error(self, ws, error):
        """
        错误处理回调
        
        Args:
            ws: WebSocket连接
            error: 错误信息
        """
        logger.error(f"WebSocket连接发生错误: {error}")
        # 标记连接已断开，触发重连
        self.is_connected = False
    
    def on_close(self, ws, close_status_code, close_msg):
        """
        连接关闭回调
        
        Args:
            ws: WebSocket连接
            close_status_code: 关闭状态码
            close_msg: 关闭消息
        """
        logger.info(f"WebSocket连接已关闭 (状态码: {close_status_code}, 消息: {close_msg})")
        self.is_connected = False
        
        # 如果应该重连且不在重连中，启动重连
        if self.should_reconnect and not self.reconnecting:
            logger.info(f"将在 {HEARTBEAT_INTERVAL} 秒后尝试重新连接...")
            threading.Thread(target=self._reconnect_after_delay, daemon=True).start()
    
    def on_open(self, ws):
        """
        连接建立回调
        
        Args:
            ws: WebSocket连接
        """
        logger.info("WebSocket连接已建立")
        self.is_connected = True
        # 启动心跳线程
        self.heartbeat_thread = threading.Thread(target=self.send_heartbeat)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()
    
    def send_heartbeat(self):
        """
        发送心跳
        """
        while self.is_connected:
            try:
                time.sleep(HEARTBEAT_INTERVAL)  # 等待心跳间隔
                if self.ws and self.is_connected:
                    self.ws.send("heartbeat")
                    logger.debug("发送心跳")
            except Exception as e:
                logger.error(f"发送心跳失败: {e}")
                # 心跳发送失败，标记连接断开，触发重连
                self.is_connected = False
                if self.should_reconnect and not self.reconnecting:
                    logger.info(f"心跳发送失败，将在 {HEARTBEAT_INTERVAL} 秒后尝试重新连接...")
                    threading.Thread(target=self._reconnect_after_delay, daemon=True).start()
                break
    
    def _reconnect_after_delay(self):
        """
        延迟后重连
        """
        if self.reconnecting:
            return
        
        self.reconnecting = True
        try:
            # 等待心跳间隔时间
            time.sleep(HEARTBEAT_INTERVAL)
            
            # 检查是否还需要重连（可能已经连接成功或主动关闭）
            if not self.should_reconnect:
                return
            
            if not self.is_connected:
                logger.info("开始尝试重新连接...")
                # 重置标志，允许 connect() 内部的重连逻辑
                self.reconnecting = False
                # 调用 connect()，这是阻塞的
                self.connect()
            else:
                # 已经连接成功，不需要重连
                logger.info("连接已恢复，取消重连")
        except Exception as e:
            logger.error(f"重连过程中发生错误: {e}")
            self.reconnecting = False
            # 如果重连失败且应该继续重连，等待心跳间隔后再次尝试
            if self.should_reconnect:
                time.sleep(HEARTBEAT_INTERVAL)
                if not self.is_connected:
                    threading.Thread(target=self._reconnect_after_delay, daemon=True).start()
        finally:
            # 确保标志被重置（如果 connect() 返回了）
            if self.reconnecting:
                self.reconnecting = False
    
    def connect(self):
        """
        建立WebSocket连接
        """
        # 启用跟踪以便调试
        # websocket.enableTrace(True)
        
        logger.info(f"尝试连接到: {self.url}")
        
        try:
            # 创建WebSocket连接
            self.ws = websocket.WebSocketApp(
                self.url,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            
            # 运行WebSocket连接（阻塞）
            # 如果连接失败或断开，run_forever 会返回，on_close 回调会处理重连
            self.ws.run_forever()
                
        except Exception as e:
            logger.error(f"连接过程中发生异常: {e}")
            self.is_connected = False
            # 如果连接失败，等待后重试（on_close 可能不会触发，所以这里需要处理）
            if self.should_reconnect and not self.reconnecting:
                logger.info(f"连接失败，将在 {HEARTBEAT_INTERVAL} 秒后尝试重新连接...")
                threading.Thread(target=self._reconnect_after_delay, daemon=True).start()
    
    def close(self):
        """
        关闭WebSocket连接
        """
        logger.info("正在关闭WebSocket连接...")
        self.should_reconnect = False  # 停止重连
        self.is_connected = False
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                logger.error(f"关闭连接时发生错误: {e}")

def main():
    """
    主函数
    """
    # 加载配置
    config_module = load_config()
    if not config_module:
        logger.error("无法加载配置文件，程序退出")
        return
    
    # 从配置读取服务器地址和端口
    server_ip = getattr(config_module, 'SERVER_IP')
    server_port = getattr(config_module, 'SERVER_PORT')
    
    if not server_ip:
        logger.error("配置文件中缺少 SERVER_IP，程序退出")
        return
    
    if server_port is None:
        logger.error("配置文件中缺少 SERVER_PORT，程序退出")
        return
    websocket_url = f"ws://{server_ip}:{server_port}/websocket"
    
    # 读取保存的 hash 值
    module_hash = read_module_hash()
    if not module_hash:
        logger.error("无法获取模块 hash 值，程序退出")
        return
    
    # 使用读取到的 hash 值创建 WebSocket 客户端
    client = WebSocketClient(websocket_url, module_hash)
    
    try:
        # 启动连接（如果断开会自动重连）
        client.connect()
        # 保持主线程运行，等待重连
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭连接...")
        client.close()
        logger.info("程序已退出")

if __name__ == "__main__":
    main()

