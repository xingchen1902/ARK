"""
Vercel Serverless Function - 飞书 API 代理
前端通过 /api/proxy 获取飞书多维表格数据
"""

import os, json
from datetime import datetime, timezone, timedelta
try:
    import requests
except ImportError:
    requests = None


def handler(request):
    """Vercel Python Serverless Function 入口"""
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

    if request.method == "OPTIONS":
        return {"statusCode": 204, "headers": headers, "body": ""}

    FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
    FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
    FEISHU_APP_TOKEN = os.environ.get("FEISHU_APP_TOKEN", "B5lBbWgjXamRS6s1CcEcTvgtnQc")
    FEISHU_TABLE_ID = os.environ.get("FEISHU_TABLE_ID", "tblVmNxjg8WjyXdw")

    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "error": "FEISHU_APP_ID or FEISHU_APP_SECRET not configured",
                "hint": "请在 Vercel 环境变量中设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET"
            })
        }

    try:
        # 获取 token
        r = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
            timeout=10
        )
        d = r.json()
        if d.get("code") != 0:
            return {"statusCode": 500, "headers": headers,
                    "body": json.dumps({"error": f"Token failed: {d.get('msg')}"})}

        token = d["tenant_access_token"]

        # 获取表格数据
        r2 = requests.get(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records?page_size=20",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15
        )
        d2 = r2.json()
        if d2.get("code") != 0:
            return {"statusCode": 500, "headers": headers,
                    "body": json.dumps({"error": f"Fetch failed: {d2.get('msg')}"})}

        BJT = timezone(timedelta(hours=8))
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

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "data": result,
                "last_update": datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")
            }, ensure_ascii=False)
        }

    except Exception as e:
        return {"statusCode": 500, "headers": headers,
                "body": json.dumps({"error": str(e)})}
