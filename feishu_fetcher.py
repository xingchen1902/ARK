#!/usr/bin/env python3
"""
ARK 飞书数据拉取器 - 从飞书多维表格拉取数据并写入 data.json
dashboard.html 直接读取 data.json 展示
"""

import os, sys, json, time, threading
from datetime import datetime, timezone, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()

BJT = timezone(timedelta(hours=8))

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "cli_a949f1b80863dbda")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "J4nvL0twSrqUCN6k1RzMudC7beg2qDhH")
FEISHU_APP_TOKEN = "B5lBbWgjXamRS6s1CcEcTvgtnQc"
FEISHU_TABLE_ID = "tblVmNxjg8WjyXdw"

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
REFRESH_INTERVAL = 300  # 5分钟

FIELD_DATE = "日期"
FIELD_BONUS_BALANCE = "奖金池余额"
FIELD_BONUS_WITHDRAW = "奖金池提取"
FIELD_DYNAMIC = "动静态涡轮"
FIELD_STATIC = "静态涡轮"
FIELD_DYNAMIC_TURBO = "动态涡轮"
FIELD_STAKE_BALANCE = "质押池余额"
FIELD_STAKE_IN = "新增质押"
FIELD_STAKE_OUT = "赎回"
FIELD_NET_STAKE = "净质押量"


def get_tenant_token():
    r = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}, timeout=10)
    d = r.json()
    if d.get("code") != 0:
        raise Exception(f"飞书 token 失败: {d}")
    return d["tenant_access_token"]


def fetch_from_feishu():
    token = get_tenant_token()
    r = requests.get(
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records?page_size=20",
        headers={"Authorization": f"Bearer {token}"}, timeout=15
    )
    d = r.json()
    if d.get("code") != 0:
        print(f"[飞书] 获取失败: {d.get('msg')}")
        return None

    items = sorted(d.get("data", {}).get("items", []), key=lambda x: x.get("fields", {}).get(FIELD_DATE, 0))
    result = []
    for item in items:
        f = item["fields"]
        ms = f.get(FIELD_DATE, 0)
        ds = datetime.fromtimestamp(ms / 1000, BJT).strftime("%Y-%m-%d") if ms else "?"
        result.append({
            "date": ds,
            "bonus_balance": float(f.get(FIELD_BONUS_BALANCE, 0)),
            "bonus_withdraw": float(f.get(FIELD_BONUS_WITHDRAW, 0)),
            "dynamic": float(f.get(FIELD_DYNAMIC, 0)),
            "static": float(f.get(FIELD_STATIC, 0)),
            "dynamic_turbo": float(f.get(FIELD_DYNAMIC_TURBO, 0)),
            "stake_balance": float(f.get(FIELD_STAKE_BALANCE, 0)),
            "stake_in": float(f.get(FIELD_STAKE_IN, 0)),
            "stake_out": float(f.get(FIELD_STAKE_OUT, 0)),
            "net_stake": float(f.get(FIELD_NET_STAKE, 0)),
        })
    return result


def refresh():
    print(f"[{datetime.now(BJT).strftime('%H:%M:%S')}] 正在从飞书拉取数据...")
    data = fetch_from_feishu()
    if data:
        with open(DATA_FILE, "w") as f:
            json.dump({
                "data": data,
                "last_update": datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")
            }, f, ensure_ascii=False)
        print(f"  [OK] {len(data)} 条数据已写入 {DATA_FILE}")
    else:
        print("  [失败]")


def periodic_refresh():
    while True:
        time.sleep(REFRESH_INTERVAL)
        refresh()


if __name__ == "__main__":
    refresh()
    print(f"定时刷新: 每 {REFRESH_INTERVAL} 秒")
    if "--once" not in sys.argv:
        t = threading.Thread(target=periodic_refresh, daemon=True)
        t.start()
        try:
            t.join()
        except KeyboardInterrupt:
            print("\n[已停止]")
