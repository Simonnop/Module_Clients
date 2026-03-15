import requests
import pysnowball as ball

r = requests.get("https://xueqiu.com/hq", headers={"user-agent": "Mozilla"})
t = r.cookies["xq_a_token"]
print(t)

ball.set_token(f'xq_a_token={t}')
print(t)
print(ball.quotec("SZ300750"))
print(ball.suggest_stock("宁德时代"))