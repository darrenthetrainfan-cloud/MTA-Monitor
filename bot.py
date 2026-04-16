import os
import requests
import json

# 配置
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def get_text_safe(obj):
    """提取原始文本，没有任何过滤"""
    if not obj or 'translation' not in obj:
        return ""
    translations = obj.get('translation', [])
    if not translations:
        return ""
    return translations[0].get('text', '').strip()

def main():
    if not WEBHOOK_URL:
        print("Webhook URL missing")
        return

    # 1. 读取历史 (兼容所有旧格式)
    seen_ids = set()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                data = json.load(f)
                seen_ids = set(data) if isinstance(data, list) else set(data.keys())
        except:
            pass

    # 2. 获取数据
    try:
        r = requests.get(DATA_URL, timeout=30)
        data = r.json()
    except:
        return

    entities = data.get('entity', [])
    new_history = []

    for entity in entities:
        alert_id = str(entity.get('id', ''))
        if not alert_id: continue
        new_history.append(alert_id)

        # 3. 发现新警报就直接发，不准拦截
        if alert_id not in seen_ids:
            alert = entity.get('alert', {})
            header = get_text_safe(alert.get('headerText'))
            description = get_text_safe(alert.get('descriptionText'))
            
            # 暴力抓取所有相关的实体信息（电梯、车站、线路）
            impact_details = []
            for info in alert.get('informedEntity', []):
                details = [f"{k}: {v}" for k, v in info.items() if v]
                if details:
                    impact_details.append(" | ".join(details))
            
            # 拼装信息，不再使用复杂的字段结构，防止格式报错
            full_msg = "**ALERT DETAILS:**\n" + (description if description else "No additional description.")
            full_msg += "\n\n**RAW ENTITIES:**\n" + ("\n".join(impact_details) if impact_details else "None")

            payload = {
                "embeds": [{
                    "title": header if header else f"MTA Alert {alert_id}",
                    "description": full_msg[:4000],
                    "color": 15548997,
                    "footer": {"text": "Alert ID: " + alert_id}
                }]
            }

            try:
                requests.post(WEBHOOK_URL, json=payload)
            except:
                pass

    # 4. 强制保存为最稳妥的列表格式
    with open(HISTORY_FILE, 'w') as f:
        json.dump(new_history, f)

if __name__ == "__main__":
    main()
