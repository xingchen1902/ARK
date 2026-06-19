#!/usr/bin/env python3
"""
ARK / gARK 代币 BSC 链数据采集 → 飞书多维表格
用法: python3 ark_feishu_collector.py [日期，如 2026-06-19]
      默认采集当天 (BJT)
"""

import os, sys, json, time, requests
from datetime import datetime, timezone, timedelta
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from dotenv import load_dotenv
load_dotenv()

# ==================== 配置 ====================

RPC_URLS = [
    "https://bsc-mainnet.nodereal.io/v1/70208501917a413bab46cb281fc0997f",
    "https://bsc.mytokenpocket.vip",
]

TOKEN_ARK = "0xCae117ca6Bc8A341D2E7207F30E180f0e5618B9D"
TOKEN_GARK = "0x911f12D137D74E5917877f87cf8A8bB2FDde557f"
DECIMALS = 18

BONUS_POOL = "0x8501168656FcaC4628F6910CcABEA8B64Ebe5BD4"
STAKE_POOL = "0xd1D95292F450b665566df4c4255615eF4Ed9BD0B"
TARGET_DYNAMIC = "0x8366a748E02F730911Cb5AB4fd049d2E1e0414b7"

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_APP_TOKEN = "B5lBbWgjXamRS6s1CcEcTvgtnQc"
FEISHU_TABLE_ID = "tblVmNxjg8WjyXdw"

FIELD_DATE = "日期"
FIELD_BONUS_BALANCE = "奖金池余额"
FIELD_BONUS_WITHDRAW = "奖金池提取"
FIELD_STATIC_WITHDRAW = "静态涡轮"
FIELD_DYNAMIC_WITHDRAW = "动静态涡轮"
FIELD_STAKE_BALANCE = "质押池余额"
FIELD_STAKE_IN = "新增质押"
FIELD_STAKE_OUT = "赎回"
FIELD_NET_STAKE = "净质押量"

BJT = timezone(timedelta(hours=8))
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
BURN_ADDR = "0x0000000000000000000000000000000000000000"
BURN_ADDR2 = "0x000000000000000000000000000000000000dead"

BLOCK_TIME = 0.45       # BSC 出块时间
BLOCKS_PER_DAY = 192000  # 一天约192000块

# ==================== RPC 工具 ====================

def rpc_call(rpc_url, method, params, retries=3):
    for i in range(retries):
        try:
            r = requests.post(rpc_url, json={"jsonrpc":"2.0","method":method,"params":params,"id":1}, timeout=20)
            d = r.json()
            if "error" in d:
                if i < retries - 1: time.sleep(1); continue
                raise Exception(d["error"]["message"])
            return d["result"]
        except Exception as e:
            if i < retries - 1: time.sleep(1); continue
            raise

def get_web3():
    for url in RPC_URLS:
        try:
            w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 15}))
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            if w3.is_connected(): return w3, url
        except: continue
    raise Exception("所有 RPC 节点均无法连接")

def raw_get_logs(rpc_url, from_block, to_block, topic_filter):
    return rpc_call(rpc_url, "eth_getLogs", [{
        "fromBlock": hex(from_block), "toBlock": hex(to_block),
        "address": TOKEN_ARK, "topics": topic_filter,
    }])

def raw_get_balance(rpc_url, token, address, block="latest"):
    data = "0x70a08231" + address[2:].lower().zfill(64)
    r = rpc_call(rpc_url, "eth_call", [{"to": token, "data": data}, hex(block) if isinstance(block, int) else block])
    return int(r, 16)

# ==================== 飞书工具 ====================

def get_tenant_token():
    r = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}, timeout=10)
    d = r.json()
    if d.get("code") != 0: raise Exception(f"获取飞书 token 失败: {d}")
    return d["tenant_access_token"]

def write_to_feishu(data):
    token = get_tenant_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records?page_size=20&field_names={FIELD_DATE}"
    r = requests.get(url, headers=headers, timeout=15)
    existing = r.json()
    if existing.get("code") == 0:
        date_ms = int(datetime.strptime(data["date"], "%Y-%m-%d").replace(tzinfo=BJT).timestamp() * 1000)
        for item in existing.get("data", {}).get("items", []):
            if item.get("fields", {}).get(FIELD_DATE) == date_ms:
                print(f"  [跳过] {data['date']} 已有记录")
                return True, item["record_id"]

    ts = int(datetime.strptime(data["date"], "%Y-%m-%d").replace(tzinfo=BJT).timestamp() * 1000)
    record = {"fields": {
        FIELD_DATE: ts,
        FIELD_BONUS_BALANCE: round(data["bonus_balance"], 2),
        FIELD_BONUS_WITHDRAW: round(data["bonus_withdraw"], 2),
        FIELD_STATIC_WITHDRAW: round(data["static_withdraw"], 2),
        FIELD_DYNAMIC_WITHDRAW: round(data["dynamic_withdraw"], 2),
        FIELD_STAKE_BALANCE: round(data["stake_balance"], 2),
        FIELD_STAKE_IN: round(data["stake_in"], 2),
        FIELD_STAKE_OUT: round(data["stake_out"], 2),
        FIELD_NET_STAKE: round(data["net_stake"], 2),
    }}

    r = requests.post(url, headers=headers, json=record, timeout=15)
    result = r.json()
    if result.get("code") == 0:
        print(f"  ✓ 飞书写入成功: {data['date']}")
        return True, result["data"]["record"]["record_id"]
    else:
        print(f"  ✗ 飞书写入失败: {result}")
        return False, None

# ==================== 主逻辑 ====================

def collect_daily(target_date_bjt):
    print(f"\n{'='*50}")
    print(f"[开始] 采集日期: {target_date_bjt}")
    print(f"{'='*50}")

    w3, rpc_url = get_web3()

    # 获取当前块信息
    current_block_hex = rpc_call(rpc_url, "eth_blockNumber", [])
    current_block = int(current_block_hex, 16)
    current_ts = int(rpc_call(rpc_url, "eth_getBlockByNumber", [current_block_hex, False])["timestamp"], 16)
    print(f"  [当前] 块 {current_block}, BJT {datetime.fromtimestamp(current_ts, BJT)}")

    date_start = datetime.strptime(target_date_bjt, "%Y-%m-%d").replace(tzinfo=BJT)
    date_end = date_start + timedelta(days=1)
    ts_start = int(date_start.timestamp())
    ts_end = int(date_end.timestamp())

    # 直接计算估算块号
    estimated_start = int(current_block - (current_ts - ts_start) / BLOCK_TIME)

    # 小范围二分精确定位 (±1000块，10次迭代)
    def find_block(target_ts, estimate):
        lo, hi = estimate - 1000, estimate + 1000
        for _ in range(12):
            if hi - lo <= 1: return hi
            mid = (lo + hi) // 2
            b = rpc_call(rpc_url, "eth_getBlockByNumber", [hex(mid), False])
            bt = int(b["timestamp"], 16)
            if bt < target_ts: lo = mid
            else: hi = mid
            time.sleep(0.05)
        return hi

    start_block = find_block(ts_start, estimated_start)
    end_block = find_block(ts_end, estimated_start + BLOCKS_PER_DAY)
    print(f"  [块范围] {start_block} ~ {end_block} ({end_block - start_block} 块)")

    if end_block <= start_block:
        print("  [跳过] 范围无效")
        return None

    CHUNK = 3000
    bonus_out_logs = []
    stake_in_logs = []
    stake_out_logs = []

    bonus_pad = "0x" + "0"*24 + BONUS_POOL[2:].lower()
    stake_pad = "0x" + "0"*24 + STAKE_POOL[2:].lower()

    for fb in range(start_block, end_block, CHUNK):
        tb = min(fb + CHUNK - 1, end_block)
        try:
            for filter_topic in [
                [TRANSFER_TOPIC, bonus_pad],
                [TRANSFER_TOPIC, None, stake_pad],
                [TRANSFER_TOPIC, stake_pad],
            ]:
                logs = raw_get_logs(rpc_url, fb, tb, filter_topic)
                if filter_topic[1] == bonus_pad:
                    bonus_out_logs.extend(logs)
                elif None in filter_topic:
                    stake_in_logs.extend(logs)
                else:
                    stake_out_logs.extend(logs)
        except Exception as e:
            print(f"  [E] {fb}~{tb}: {str(e)[:50]}")
        time.sleep(0.3)

    bonus_out = sum(int(l["data"], 16) for l in bonus_out_logs) / 10**DECIMALS
    stake_in = sum(int(l["data"], 16) for l in stake_in_logs) / 10**DECIMALS
    stake_out = sum(int(l["data"], 16) for l in stake_out_logs) / 10**DECIMALS

    bonus_bal = raw_get_balance(rpc_url, TOKEN_ARK, BONUS_POOL) / 10**DECIMALS
    stake_bal = raw_get_balance(rpc_url, TOKEN_ARK, STAKE_POOL) / 10**DECIMALS

    # ========== gARK 销毁 ==========
    print(f"\n--- gARK 销毁 ---")
    gark_burn = 0
    burn_pad0 = "0x" + "0"*24 + BURN_ADDR[2:].lower()
    burn_pad1 = "0x" + "0"*24 + BURN_ADDR2[2:].lower()

    for fb in range(start_block, end_block, CHUNK):
        tb = min(fb + CHUNK - 1, end_block)
        try:
            for pad in [burn_pad0, burn_pad1]:
                logs = rpc_call(rpc_url, "eth_getLogs", [{
                    "fromBlock": hex(fb), "toBlock": hex(tb),
                    "address": TOKEN_GARK,
                    "topics": [TRANSFER_TOPIC, None, pad],
                }])
                for l in logs:
                    gark_burn += int(l["data"], 16)
        except Exception as e:
            print(f"  [E] gARK {fb}~{tb}: {str(e)[:50]}")
        time.sleep(0.3)

    static_withdraw = gark_burn / 10**DECIMALS

    # ========== 动静态涡轮（目标地址接收的ARK） ==========
    print(f"\n--- 动静态涡轮 ---")
    dynamic_total = 0
    target_pad = "0x" + "0"*24 + TARGET_DYNAMIC[2:].lower()
    for fb in range(start_block, end_block, CHUNK):
        tb = min(fb + CHUNK - 1, end_block)
        try:
            logs = rpc_call(rpc_url, "eth_getLogs", [{
                "fromBlock": hex(fb), "toBlock": hex(tb),
                "address": TOKEN_ARK,
                "topics": [TRANSFER_TOPIC, None, target_pad],
            }])
            for l in logs:
                dynamic_total += int(l["data"], 16)
        except Exception as e:
            print(f"  [E] 动静态涡轮 {fb}~{tb}: {str(e)[:50]}")
        time.sleep(0.3)

    dynamic_withdraw = dynamic_total / 10**DECIMALS
    print(f"  动静态涡轮: {dynamic_withdraw:.2f}")

    net_stake = stake_in - stake_out - bonus_out

    print(f"\n  [结果]")
    print(f"    奖金池提取: {bonus_out:.2f}")
    print(f"    静态涡轮(gARK销毁): {static_withdraw:.2f}")
    print(f"    动静态涡轮: {dynamic_withdraw:.2f}")
    print(f"    新增质押: {stake_in:.2f}")
    print(f"    赎回: {stake_out:.2f}")
    print(f"    奖金池余额: {bonus_bal:.2f}")
    print(f"    质押池余额: {stake_bal:.2f}")
    print(f"    净质押: {net_stake:.2f}")

    return {
        "date": target_date_bjt,
        "bonus_balance": bonus_bal,
        "bonus_withdraw": bonus_out,
        "static_withdraw": static_withdraw,
        "dynamic_withdraw": bonus_out,
        "stake_balance": stake_bal,
        "stake_in": stake_in,
        "stake_out": stake_out,
        "net_stake": net_stake,
    }

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print("用法: python3 ark_feishu_collector.py [日期，如 2026-06-19]")
        print("      默认采集当天 (BJT)")
        sys.exit(0)

    target_date = sys.argv[1] if len(sys.argv) > 1 else datetime.now(BJT).strftime("%Y-%m-%d")
    summary = collect_daily(target_date)
    if summary:
        print(f"\n{'='*50}")
        print(f"[写入] 飞书多维表格")
        write_to_feishu(summary)
        print(f"{'='*50}")
    else:
        sys.exit(1)
