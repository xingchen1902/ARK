#!/usr/bin/env python3
"""
ARK 数据 Telegram 机器人 - 命令响应服务
- 后台运行，响应群内 /7days /today /help 命令
- 提供 push_data() 函数供采集脚本采集完成后调用
- 不负责定时推送，采集脚本采集完自己调用推送

用法:
  python3 telegram_bot.py              # 启动命令监听服务
  python3 telegram_bot.py --push <record_json>  # 推送一条数据（被采集脚本调用）
  python3 telegram_bot.py --push-data  # 从 data.json 推送最新一条
"""

import os, sys, json, time, argparse, threading, subprocess
from datetime import datetime, timezone, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()

BJT = timezone(timedelta(hours=8))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")

# ==================== Telegram 配置 ====================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_chat_id_str = os.environ.get("TELEGRAM_CHAT_ID", "")
CHAT_ID = int(_chat_id_str) if _chat_id_str.lstrip("-").isdigit() else _chat_id_str
LAST_UPDATE_ID = 0

def fmt_num(n):
    return f"{n:,.2f}"

# ==================== 发送消息 ====================

def send_telegram(message, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        d = r.json()
        if d.get("ok"):
            return True
        else:
            print(f"[Telegram] 发送失败: {d.get('description', d)}")
            return False
    except Exception as e:
        print(f"[Telegram] 请求异常: {e}")
        return False


def send_to_chat(chat_id, message, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        d = r.json()
        if d.get("ok"):
            return True
        else:
            print(f"[Telegram] 回复失败: {d.get('description', d)}")
            return False
    except Exception as e:
        print(f"[Telegram] 回复异常: {e}")
        return False


# ==================== 数据加载 ====================

def load_data():
    if not os.path.exists(DATA_FILE):
        return [], None
    with open(DATA_FILE) as f:
        d = json.load(f)
    return d.get("data", []), d.get("last_update", "")


# ==================== 格式化消息 ====================
def push_data(record):
    """推送一条采集记录到群组（被采集脚本调用）"""
    msg = build_daily_msg(record)
    ok = send_telegram(msg)
    if ok:
        log(f"已推送 {record.get('date','?')} 数据到群组")
    return ok
def poll_commands():
    """轮询 getUpdates 响应群内命令"""
    global LAST_UPDATE_ID

    log("命令监听服务已启动")
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {
                "offset": LAST_UPDATE_ID + 1,
                "timeout": 30,
                "allowed_updates": ["message"],
            }
            r = requests.get(url, params=params, timeout=35)
            d = r.json()
            if not d.get("ok"):
                time.sleep(5)
                continue

            for update in d.get("result", []):
                update_id = update.get("update_id", 0)
                if update_id > LAST_UPDATE_ID:
                    LAST_UPDATE_ID = update_id

                msg = update.get("message", {})
                text = msg.get("text", "").strip()
                chat_id = msg.get("chat", {}).get("id")

                if chat_id != CHAT_ID:
                    continue

                if text in ("/help", "/start"):
                    help_text = """<b>🤖 ARK 数据机器人</b>

采集完成后自动推送数据到群组

数据来源：BSC 链上 · 飞书多维表格"""
                    send_to_chat(chat_id, help_text)
                    log("回复 /help")

        except requests.Timeout:
            pass
        except Exception as e:
            print(f"[轮询] 异常: {e}")
            time.sleep(5)


# ==================== 辅助 ====================

def log(msg):
    ts = datetime.now(BJT).strftime("%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


# ==================== 入口 ====================

def main():
    parser = argparse.ArgumentParser(description="ARK 数据 Telegram 机器人")
    parser.add_argument("--push", type=str, help="推送一条数据（JSON 字符串）")
    parser.add_argument("--push-data", action="store_true", help="从 data.json 推送最新一条")
    args = parser.parse_args()

    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("错误: 请在 .env 中设置 TELEGRAM_BOT_TOKEN")
        sys.exit(1)
    if not CHAT_ID or CHAT_ID == "YOUR_CHAT_ID_HERE":
        print("错误: 请在 .env 中设置 TELEGRAM_CHAT_ID")
        sys.exit(1)

    # 推送模式（被采集脚本调用）
    if args.push:
        record = json.loads(args.push)
        push_data(record)
        return

    if args.push_data:
        push_today()
        return

    # 命令监听服务模式
    log("机器人启动")

    # 发送启动通知
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": "🤖 ARK 数据机器人已启动\n发送 /help 查看可用命令"},
            timeout=10
        )
        if r.json().get("ok"):
            log("启动通知已发送到群组")
        else:
            log(f"启动通知发送失败: {r.json().get('description')}")
    except Exception as e:
        log(f"启动通知异常: {e}")

    poll_commands()


if __name__ == "__main__":
    main()
