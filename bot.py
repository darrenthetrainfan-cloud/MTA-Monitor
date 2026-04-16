import os
import requests
import json

# 配置
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
# 四个专用数据源
SOURCES = {
    "Subway": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts",
    "Bus": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fbus-alerts",
    "LIRR": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Flirr-alerts",
    "MNR": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fmnr-alerts"
}
HISTORY_FILE = "alert_history.json"

def get_text_safe(obj):
    """提取原始文本，没有任何排除"""
    if not obj or 'translation' not in obj:
        return ""
    translations = obj.get('translation', [])
    if not translations:
        return ""
    return translations[0].get('text', '').strip()

def main():
    if not WEBHOOK_URL:
        print("WEBHOOK_URL is missing")
        return

    # 1. 读取历史 (兼容列表和字典)
    seen_ids = set()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                data = json.load(f)
                seen_ids = set(data) if isinstance(data, list) else set(data.keys())
        except:
            pass

    new_history = []
    
    # 2. 遍历所有数据源
    for mode, url in SOURCES.items():
        print("Fetching " + mode + "...")
        try:
            r = requests.get(url, timeout=30)
            data = r.json()
            entities = data.get('entity', [])
        except Exception as e:
            print("Error fetching " + mode + ": " + str(e))
            continue

        for entity in entities:
            alert_id = str(entity.get('id', ''))
            if not alert_id: continue
            new_history.append(alert_id)

            # 3. 发现新 ID 直接发送，不做任何过滤
            if alert_id not in seen_ids:
                alert = entity.get('alert', {})
                header = get_text_safe(alert.get('headerText'))
                description = get_text_safe(alert.get('descriptionText'))
                
                # 抓取 Informed Entities (线路、车站、设施 ID)
                impact_list = []
                for info in alert.get('informedEntity', []):
                    details = [k + ": " + str(v) for k, v in info.items() if v]
                    if details:
                        impact_list.append(" | ".join(details))
                
                # 拼装消息体
                content = "**Details:**\n" + (description if description else "No description provided.")
                content += "\n\n**Informed Entities:**\n" + ("\n".join(impact_list) if impact_list else "None")

                payload = {
                    "embeds": [{
                        "title": "[" + mode + "] " + (header if header else "New Alert"),
                        "description": content[:4000],
                        "color": 15844367, # 亮黄色
                        "footer": {"text": "Alert ID: " + alert_id}
                    }]
                }

                try:
                    requests.post(WEBHOOK_URL, json=payload)
                except:
                    pass

    # 4. 保存最新的全量 ID 列表
    with open(HISTORY_FILE, 'w') as f:
        json.dump(new_history, f)
    print("Execution finished.")

if __name__ == "__main__":
    main()
