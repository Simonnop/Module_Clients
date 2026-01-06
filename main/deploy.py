import asyncio
from bilibili_api import user, sync
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


user_list = [
    {
        'name': '擒龙先生',
        'uid': '3546929266952873',
    },
    {
        'name': '战国时代姜汁汽水',
        'uid': '1039025435',
    },
    {
        'name': '波段哥王安松',
        'uid': '697048631',
    }
]

async def get_dynamics(user_info):
    # 实例化
    u = user.User(user_info['uid'])

    # # 用于记录下一次起点
    offset = ""

    # 用于存储所有动态
    dynamics = []

    page = await u.get_dynamics_new(offset)

    dynamics.extend(page["items"])

    return dynamics

def split_av_and_draw(user_list, look_days):
    av_list = []
    draw_list = []
    for user in user_list:
        dynamics = sync(get_dynamics(user))
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
                        'date': str(date.strftime('%Y-%m-%d'))
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
                        'date': str(date.strftime('%Y-%m-%d'))
                    })
            except Exception as e:
                print(e)
    return av_list, draw_list

def get_subtitle(av_list):
    subtitle_list = []
    for av in av_list:
        print('now processing: ', av['name'], av['url'])
        # 
        result = subprocess.run(["bash", 'run.bash', av['url']], capture_output=True, text=True)
        print(result.stdout)
        print(result.stderr)

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
                'content': text_content
            })
            print('done')
        else:
            print(f"not found")
    return subtitle_list

def do_crawl():
    look_days = 1
    av_list, draw_list = split_av_and_draw(user_list, look_days)
    subtitle_list = get_subtitle(av_list)
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
    mongodb_uri = 'mongodb://admin:Glgl1234567@119.45.129.116:27017/?authSource=admin'  # MongoDB 连接 URI
    database_name = 'finance_data'  # 数据库名称
    collection_name = 'bili_info'  # 集合名称
    
    try:
        client = MongoClient(mongodb_uri)
        db = client[database_name]
        print(f"成功连接到 MongoDB: {mongodb_uri}")
    except Exception as e:
        print(f"连接 MongoDB 失败: {str(e)}")
        return f"连接 MongoDB 失败: {str(e)}"
    collection = db[collection_name]
    if len(info_list) > 0:
        collection.insert_many(info_list)
        return f"插入{len(info_list)}条数据"
    else:
        return "没有数据需要插入"