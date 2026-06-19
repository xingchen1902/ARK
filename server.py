#!/usr/bin/env python3
"""
ARK Dashboard 后端 - 定期从飞书多维表格拉取数据并提供 API
"""

import os, json, time, threading
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

# ==================== 配置 ====================

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "cli_a949f1b80863dbda")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "J4nvL0twSrqUCN6k1RzMudC7beg2qDhH")
FEISHU_APP_TOKEN = "B5lBbWgjXamRS6s1CcEcTvgtnQc"
FEISHU_TABLE_ID = "tblVmNxjg8WjyXdw"
PORT = int(os.environ.get("PORT", 8899))
REFRESH_INTERVAL = 300  # 5分钟刷新一次

BJT = timezone(timedelta(hours=8))

# ==================== 数据缓存 ====================

cache = {"data": [], "last_update": None}
lock = threading.Lock()

def get_tenant_token():
    r = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}, timeout=10)
    d = r.json()
    if d.get("code") != 0:
        raise Exception(f"飞书 token 失败: {d}")
    return d["tenant_access_token"]

def fetch_from_feishu():
    """从飞书获取多维表格数据"""
    try:
        token = get_tenant_token()
        r = requests.get(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records?page_size=20",
            headers={"Authorization": f"Bearer {token}"}, timeout=15
        )
        d = r.json()
        if d.get("code") != 0:
            print(f"[飞书] 获取失败: {d.get('msg')}")
            return None

        items = sorted(d.get("data", {}).get("items", []), key=lambda x: x.get("fields", {}).get("日期", 0))
        result = []
        for item in items:
            f = item["fields"]
            ms = f.get("日期", 0)
            ds = datetime.fromtimestamp(ms / 1000, BJT).strftime("%Y-%m-%d") if ms else "?"
            result.append({
                "date": ds,
                "bonus_balance": float(f.get("奖金池余额", 0)),
                "bonus_withdraw": float(f.get("奖金池提取", 0)),
                "dynamic": float(f.get("动静态涡轮", 0)),
                "static": float(f.get("静态涡轮", 0)),
                "dynamic_turbo": float(f.get("动态涡轮", 0)),
                "stake_balance": float(f.get("质押池余额", 0)),
                "stake_in": float(f.get("新增质押", 0)),
                "stake_out": float(f.get("赎回", 0)),
                "net_stake": float(f.get("净质押量", 0)),
            })

        return result
    except Exception as e:
        print(f"[飞书] 请求异常: {e}")
        return None

def refresh_cache():
    """刷新缓存"""
    data = fetch_from_feishu()
    if data:
        with lock:
            cache["data"] = data
            cache["last_update"] = datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")
        print(f"[缓存] 已更新 {len(data)} 条数据 @ {cache['last_update']}")
    else:
        print("[缓存] 刷新失败，使用旧数据")

def periodic_refresh():
    """定时刷新"""
    while True:
        time.sleep(REFRESH_INTERVAL)
        refresh_cache()

# ==================== HTTP 服务 ====================

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with lock:
                resp = json.dumps({
                    "data": cache["data"],
                    "last_update": cache["last_update"],
                }, ensure_ascii=False)
            self.wfile.write(resp.encode("utf-8"))
        elif self.path == "/dashboard.html" or self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            try:
                with open(os.path.join(os.path.dirname(__file__), "dashboard.html"), "rb") as f:
                    self.wfile.write(f.read())
            except:
                self.wfile.write(b"<h1>dashboard.html not found</h1>")
        elif self.path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            with lock:
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "records": len(cache["data"]),
                    "last_update": cache["last_update"],
                }).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def log_message(self, format, *args):
        print(f"[{datetime.now(BJT).strftime('%H:%M:%S')}] {args[0]} {args[1]}")

# ==================== 启动 ====================

if __name__ == "__main__":
    # 首次加载
    print("[启动] 首次加载飞书数据...")
    refresh_cache()

    # 启动定时刷新线程
    t = threading.Thread(target=periodic_refresh, daemon=True)
    t.start()

    # 启动 HTTP 服务
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[服务] http://localhost:{PORT}/dashboard.html")
    print(f"[API]  http://localhost:{PORT}/api/data")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[服务] 已停止")
