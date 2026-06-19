from http.server import BaseHTTPRequestHandler
import os, json
from datetime import datetime, timezone, timedelta
import requests


BJT = timezone(timedelta(hours=8))

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_APP_TOKEN = os.environ.get("FEISHU_APP_TOKEN", "B5lBbWgjXamRS6s1CcEcTvgtnQc")
FEISHU_TABLE_ID = os.environ.get("FEISHU_TABLE_ID", "tblVmNxjg8WjyXdw")

FIELD_MAP = {
    "日期": "date",
    "奖金池余额": "bonus_balance",
    "奖金池提取": "bonus_withdraw",
    "动静态涡轮": "dynamic",
    "静态涡轮": "static",
    "动态涡轮": "dynamic_turbo",
    "质押池余额": "stake_balance",
    "新增质押": "stake_in",
    "赎回": "stake_out",
    "净质押量": "net_stake",
}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

        if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
            self.wfile.write(json.dumps({
                "error": "FEISHU_APP_ID 或 FEISHU_APP_SECRET 未配置",
                "hint": "请在 Vercel 环境变量中设置"
            }, ensure_ascii=False).encode("utf-8"))
            return

        try:
            r = requests.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
                timeout=10
            )
            d = r.json()
            if d.get("code") != 0:
                self.wfile.write(json.dumps({"error": f"Token 失败: {d.get('msg')}"},
                    ensure_ascii=False).encode("utf-8"))
                return

            token = d["tenant_access_token"]

            r2 = requests.get(
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records?page_size=20",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15
            )
            d2 = r2.json()
            if d2.get("code") != 0:
                self.wfile.write(json.dumps({"error": f"获取失败: {d2.get('msg')}"},
                    ensure_ascii=False).encode("utf-8"))
                return

            items = sorted(d2.get("data", {}).get("items", []),
                           key=lambda x: x.get("fields", {}).get("日期", 0))

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

            self.wfile.write(json.dumps({
                "data": result,
                "last_update": datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")
            }, ensure_ascii=False).encode("utf-8"))

        except Exception as e:
            self.wfile.write(json.dumps({"error": str(e)},
                ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
