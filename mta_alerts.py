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
    # 1. 加载本地状态（已发送的警报 ID），防止每次运行都重复发送
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            try:
                seen_alerts = set(json.load(f))
            except json.JSONDecodeError:
                seen_alerts = set()
    else:
        seen_alerts = set()

    # 2. 获取 MTA GTFS-Realtime 数据
    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        response = requests.get(FEED_URL, timeout=15)
        response.raise_for_status()
        feed.ParseFromString(response.content)
    except Exception as e:
        print(f"获取或解析 MTA 数据失败: {e}")
        return

    current_alerts = set()
    new_alerts_sent = 0

    # 3. 遍历实体，解析警报并发送
    for entity in feed.entity:
        if entity.HasField('alert'):
            alert_id = entity.id
            current_alerts.add(alert_id)

            # 如果这是一个新警报
            if alert_id not in seen_alerts:
                send_to_discord(entity.alert, alert_id)
                seen_alerts.add(alert_id)
                new_alerts_sent += 1
                # 暂停 1 秒，防止短时间内发送过多请求导致 Discord 封禁 Webhook (Rate Limit)
                time.sleep(1) 

    # 4. 更新状态文件
    # 取 "已处理过的" 和 "当前活跃的" 警报的交集
    # 这样当 MTA 撤销某个警报时，它也会从我们的记录中移除；防止文件无限变大。
    active_seen_alerts = seen_alerts.intersection(current_alerts)

    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(active_seen_alerts), f)
    
    print(f"运行完毕。发现 {len(current_alerts)} 个当前警报，推送了 {new_alerts_sent} 个新警报。")

def send_to_discord(alert, alert_id):
    """格式化警报并发送至 Discord Webhook"""
    
    # 提取标题
    header = "MTA Service Alert"
    if alert.header_text.translation:
         # 通常第一项是英语
        header = alert.header_text.translation[0].text
    
    # 提取详细描述
    desc = "No description available."
    if alert.description_text.translation:
        desc = alert.description_text.translation[0].text
        # Discord Embed 描述上限为 4096 字符，进行安全截断
        if len(desc) > 4000:
            desc = desc[:4000] + "...\n*[Text truncated]*"

    # 提取受影响的线路
    affected_lines = set()
    for entity in alert.informed_entity:
        if entity.route_id:
            affected_lines.add(entity.route_id)
    
    lines_str = ", ".join(affected_lines) if affected_lines else "System-wide / Unknown"

    # 构建 Discord Embed 格式的 JSON 载荷
    embed = {
        "title": header[:256],
        "description": desc,
        "color": 16711680, # 红色，代表警报
        "fields": [
            {"name": "Affected Lines", "value": lines_str, "inline": False},
        ],
        "footer": {"text": f"Alert ID: {alert_id} • MTA API"}
    }

    try:
        requests.post(WEBHOOK_URL, json={"embeds": [embed]})
    except Exception as e:
        print(f"发送 Webhook 失败 [{alert_id}]: {e}")

if __name__ == "__main__":
    if not WEBHOOK_URL:
        print("错误: 未检测到 DISCORD_WEBHOOK 环境变量。")
    else:
        main()
