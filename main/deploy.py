import asyncio
from bilibili_api import user, Credential
import datetime
import subprocess
import os
import json
from pymongo import MongoClient
import os

# 1. 获取当前脚本的绝对路径
file_path = os.path.abspath(__file__)
# 2. 获取该文件所属的目录
current_dir = os.path.dirname(file_path)
# 3. 切换到该目录
os.chdir(current_dir)

DATABASE_NAME = 'finance_data'
COLLECTION_WATCH_USER = 'bili_watch_user'
COLLECTION_INFO = 'bili_info'

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
        return None

async def get_dynamics(user_info):
    # 加载凭证以避免 API 限制
    credential = None
    if os.path.exists('config.json'):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                creds = config_data.get('credentials', {})
                if creds:
                    credential = Credential(
                        sessdata=creds.get('sessdata'),
                        bili_jct=creds.get('bili_jct'),
                        buvid3=creds.get('buvid3')
                    )
        except Exception as e:
            print(f"Warning: Failed to load credentials: {e}")

    # 实例化
    u = user.User(user_info['uid'], credential=credential)

    # # 用于记录下一次起点
    offset = ""

    # 用于存储所有动态
    dynamics = []

    try:
        page = await u.get_dynamics_new(offset)
        if page and "items" in page:
            dynamics.extend(page["items"])
    except Exception as e:
        print(f"Error getting dynamics for user {user_info.get('uid')}: {e}")
        if "Expecting value" in str(e):
            print("Tip: Bilibili API 返回非 JSON 响应，请检查账号 Cookie 是否有效。")

    return dynamics

async def split_av_and_draw(user_list, look_days):
    av_list = []
    draw_list = []
    for user in user_list:
        dynamics = await get_dynamics(user)
        for dy in dynamics:
            try:
                if dy["type"] == 'DYNAMIC_TYPE_AV':
                    url = dy["modules"]["module_dynamic"]["major"]["archive"]["jump_url"]
                    date = dy["modules"]["module_author"]["pub_ts"]
                    date = datetime.datetime.fromtimestamp(int(date))
                    if date < datetime.datetime.now() - datetime.timedelta(days=look_days):
                        continue
                    url = 'http:' + url
                    av_list.append({
                        'name': user['name'],
                        'type': '视频',
                        'url': url,
                        'time': str(date.strftime('%H:%M:%S')),
                        'date': str(date.strftime('%Y-%m-%d')),
                        'used': False,
                    })
                elif dy["type"] == 'DYNAMIC_TYPE_DRAW':
                    url = dy["modules"]["module_dynamic"]["major"]["opus"]["jump_url"]
                    text = dy["modules"]["module_dynamic"]['major']["opus"]["summary"]["text"]
                    title = dy["modules"]["module_dynamic"]['major']["opus"]["title"]
                    date = dy["modules"]["module_author"]["pub_ts"]
                    date = datetime.datetime.fromtimestamp(int(date))
                    url = 'http:' + url
                    if date < datetime.datetime.now() - datetime.timedelta(days=look_days):
                        continue
                    draw_list.append({
                        'name': user['name'],
                        'type': '动态',
                        'url': url,
                        'content': '【' + title + '】' + '\n' + text,
                        'time': str(date.strftime('%H:%M:%S')),
                        'date': str(date.strftime('%Y-%m-%d')),
                        'used': False
                    })
            except Exception as e:
                print(e)
    return av_list, draw_list

async def get_subtitle(av_list):
    subtitle_list = []
    for av in av_list:
        print('now processing: ', av['name'], av['url'])
        # 
        proc = await asyncio.create_subprocess_exec(
            "bash", 'run.bash', av['url'],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        print(stdout.decode())
        print(stderr.decode())

        # 获取 bv号，用于输出文件名
        bv = av['url'].split('/video/')[1].split('/')[0]
        output_path = os.path.join('output', f'{bv}.txt')
        text_content = ""
        if os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            # 输出读取到的内容
            subtitle_list.append({
                'name': av['name'],
                'type': av['type'],
                'url': av['url'],
                'time': str(av['time']),
                'date': str(av['date']),
                'content': text_content,
                'used': False
            })
            print('done')
        else:
            print(f"not found")
    return subtitle_list

async def do_crawl():
        # 加载配置
    config_module = load_config()
    if not config_module:
        print("无法加载配置文件，程序退出")
        return
        
    # 从配置读取mongodb地址和数据库名称
    MONGODB_URI = getattr(config_module, 'MONGODB_HOST')
    try:
        client = MongoClient(MONGODB_URI)
        db = client[DATABASE_NAME]
        user_collection = db[COLLECTION_WATCH_USER]
        # remove _id from result to clean up, though not strictly necessary if downstream ignores it.
        # But pymongo returns it.
        user_list = list(user_collection.find())
    except Exception as e:
        print(f"Fetch user list failed: {str(e)}")
        return f"Fetch user list failed: {str(e)}"

    look_days = 1
    av_list, draw_list = await split_av_and_draw(user_list, look_days)
    subtitle_list = await get_subtitle(av_list)
    # 合并 av 和 draw 列表
    info_list = subtitle_list
    info_list.extend(draw_list)
    for info in info_list:
        print(info['name'])
        print(info['type'])
        print(info['url'])
        print(info['date'])
        print(info['time'])
        print(info['content'][0:100])
        print('--------------------------------')

    # # 输出 info_list 到 json 文件
    # with open('info_list.json', 'w', encoding='utf-8') as f:
    #     json.dump(info_list, f, ensure_ascii=False, indent=2)
    
    try:
        client = MongoClient(MONGODB_URI)
        db = client[DATABASE_NAME]
        print(f"成功连接到 MongoDB: {MONGODB_URI}")
    except Exception as e:
        print(f"连接 MongoDB 失败: {str(e)}")
        return f"连接 MongoDB 失败: {str(e)}"
    collection = db[COLLECTION_INFO]
    if len(info_list) > 0:
        collection.insert_many(info_list)
        return f"插入{len(info_list)}条数据"
    else:
        return "没有数据需要插入"