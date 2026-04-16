import os
import requests
import json

# 配置环境变量
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
# 使用全量 JSON 警报源
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def get_mta_text(obj):
    """从 MTA 复杂的翻译结构中提取文字，不做任何多余过滤"""
    if not obj or 'translation' not in obj:
        return ""
    translations = obj.get('translation', [])
    if not translations:
        return ""
    # 优先取第一条翻译内容
    return translations[0].get('text', '').strip()

def main():
    if not WEBHOOK_URL:
        print("Missing Discord Webhook URL.")
        return

    # 1. 加载历史记录 (强制兼容格式)
    old_history = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                raw_data = json.load(f)
                # 无论存的是什么，都转成字典 key
                if isinstance(raw_data, list):
                    old_history = {str(i): True for i in raw_data}
                elif isinstance(raw_data, dict):
                    old_history = raw_data
        except:
            old_history = {}

    # 2. 获取 API 数据
    try:
        response = requests.get(DATA_URL, timeout=20)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Fetch Error: {e}")
        return

    entities = data.get('entity', [])
    current_history = {} # 用于保存本次运行的所有 ID

    for entity in entities:
        alert_id = str(entity.get('id', ''))
        if not alert_id:
            continue
        
        current_history[alert_id] = True # 标记为已知
        
        # 3. 如果是全新 ID，执行推送逻辑
        if alert_id not in old_history:
            alert = entity.get('alert', {})
            
            # 提取文本内容
            title = get_mta_text(alert.get('headerText'))
            description = get_mta_text(alert.get('descriptionText'))
            
            # 提取受影响的具体对象 (线路、车站、设施)
            impacted_entities = []
            for info in alert.get('informedEntity', []):
                # 优先级：线路ID > 车站ID > 机构ID
                target = info.get('routeId') or info.get('stopId') or info.get('agencyId')
                if target and target not in impacted_entities:
                    impacted_entities.append(target)
            
            impact_str = ", ".join(impacted_entities) if impacted_entities else "General/System"

            # 构造 Discord Embed
            payload = {
                "embeds": [{
                    "title": title if title else "MTA Notification",
                    "description": description if description else "No additional description available.",
                    "fields": [
                        {"name": "Location / Impacted", "value": f"**{impact_str}**", "inline": False}
                    ],
                    "footer": {"text": f"Alert ID: {alert_id}"},
                    "color": 3447003 # 蓝色，代表系统消息
                }]
            }

            # 执行推送
            try:
                requests.post(WEBHOOK_URL, json=payload)
            except:
                pass

    # 4. 保存历史记录
    with open(HISTORY_FILE, 'w') as f:
        json.dump(current_history, f)
    print(f"Processed {len(entities)} alerts. History updated.")

if __name__ == "__main__":
    main()
