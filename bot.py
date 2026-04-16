import os
import requests
import json

WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def get_text(obj):
    if not obj: return ""
    translations = obj.get('translation', [])
    if translations:
        return translations[0].get('text', '').strip()
    return ""

def main():
    if not WEBHOOK_URL: return

    try:
        response = requests.get(DATA_URL)
        if response.status_code != 200: return
        
        data = response.json()
        entities = data.get('entity', [])
        
        # 加载历史记录
        old_history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    data_load = json.load(f)
                    # 兼容性处理：如果是字典则取 key，如果是列表则直接用
                    old_history = list(data_load.keys()) if isinstance(data_load, dict) else data_load
            except:
                old_history = [] 

        current_ids = []
        new_count = 0

        for entity in entities:
            alert = entity.get('alert')
            if not alert: continue
            
            alert_id = str(entity.get('id'))
            current_ids.append(alert_id)
                
            # 如果是新警报
            if alert_id not in old_history:
                header = get_text(alert.get('headerText'))
                desc = get_text(alert.get('descriptionText'))
                
                # 提取受影响线路
                affected = []
                for ent in alert.get('informedEntity', []):
                    rid = ent.get('routeId')
                    if rid and rid not in affected:
                        affected.append(rid)
                
                lines_str = ", ".join(affected) if affected else "System-wide"
                
                # 构造 Discord Embed
                payload = {
                    "embeds": [{
                        "title": header if header else "MTA Alert",
                        "description": desc if desc else "No details provided.",
                        "fields": [
                            {"name": "Affected Lines", "value": f"**{lines_str}**", "inline": False}
                        ],
                        "footer": {"text": f"Alert ID: {alert_id}"},
                        "color": 15158332 # 红色
                    }]
                }
                
                if new_count < 10: # 限制单次发送数量防止刷屏
                    requests.post(WEBHOOK_URL, json=payload)
                    new_count += 1

        # 保存当前所有 ID 到历史记录
        with open(HISTORY_FILE, 'w') as f:
            json.dump(current_ids, f)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
