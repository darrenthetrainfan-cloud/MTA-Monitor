import os
import json
import time
import requests
from google.transit import gtfs_realtime_pb2

# --- 配置区 ---
FEED_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
STATE_FILE = "seen_alerts.json"

def main():
    # 1. 加载本地状态
    seen_alerts = set()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    seen_alerts = set(json.load(f))
        except (json.JSONDecodeError, Exception) as e:
            print(f"读取状态文件失败: {e}，将重新创建。")

    # 2. 获取 MTA 数据
    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        response = requests.get(FEED_URL, timeout=20)
        response.raise_for_status()
        feed.ParseFromString(response.content)
    except Exception as e:
        print(f"获取 MTA 数据失败: {e}")
        return

    current_all_ids = set()
    to_send = []

    # 3. 预筛选新警报
    for entity in feed.entity:
        if entity.HasField('alert'):
            alert_id = str(entity.id)
            current_all_ids.add(alert_id)
            if alert_id not in seen_alerts:
                to_send.append(entity)

    print(f"当前活跃警报总数: {len(current_all_ids)}，待处理新警报: {len(to_send)}")

    # 4. 执行发送逻辑（带防刷屏保护）
    if len(to_send) > 15:
        print("检测到大量新警报，可能是首次运行或数据重置。执行静默模式，仅更新索引。")
        for entity in to_send:
            seen_alerts.add(str(entity.id))
    else:
        for entity in to_send:
            alert_id = str(entity.id)
            send_to_discord(entity.alert, alert_id)
            seen_alerts.add(alert_id)
            time.sleep(1.5)  # 严格限制速度，保护 Discord Webhook

    # 5. 清理过期的 Alert ID (只保留当前还在活跃的 ID，防止 JSON 文件无限变大)
    updated_seen = seen_alerts.intersection(current_all_ids)

    # 6. 写回文件
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(updated_seen), f)
    
    print("状态已保存。")

def send_to_discord(alert, alert_id):
    header = "MTA Service Alert"
    if alert.header_text.translation:
        header = alert.header_text.translation[0].text
    
    desc = "No details provided."
    if alert.description_text.translation:
        desc = alert.description_text.translation[0].text
        if len(desc) > 1000: # 缩短长度，避免消息过长
            desc = desc[:1000] + "..."

    affected_lines
