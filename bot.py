import os
import requests
import json

WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
# This is the all-alerts endpoint
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def main():
    if not WEBHOOK_URL:
        print("Error: Webhook URL is missing!")
        return

    try:
        # 1. Fetch Data
        response = requests.get(DATA_URL)
        if response.status_code != 200:
            print(f"Failed to fetch MTA data: {response.status_code}")
            return
        
        data = response.json()
        entities = data.get('entity', [])
        # 新增日志：看看 API 到底传回了多少个原始数据块
        print(f"Successfully fetched MTA data. Total entities in API: {len(entities)}")
        
        # 2. Load History (增加防损坏机制)
        old_history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    old_history = json.load(f)
            except json.JSONDecodeError:
                print("History file is empty or corrupted. Starting fresh.")
                old_history = [] 

        current_alerts = {}
        
        # 3. Parse Alerts (优化提取逻辑)
        for entity in entities:
            alert = entity.get('alert')
            if not alert: 
                continue
            
            # 分别提取描述和标题 (更加稳定)
            desc_obj = alert.get('descriptionText', {})
            header_obj = alert.get('headerText', {})
            
            desc_text = desc_obj.get('translation', [{}])[0].get('text', '').strip() if desc_obj else ""
            header_text = header_obj.get('translation', [{}])[0].get('text', '').strip() if header_obj else ""
            
            # 优先使用描述，如果没有描述则使用标题
            content = desc_text if desc_text else header_text
            
            # 提取受影响的线路 (去重)
            affected = []
            for ent in alert.get('informedEntity', []):
                route_id = ent.get('routeId')
                if route_id and route_id not in affected:
                    affected.append(route_id)
                    
            lines = ", ".join(affected) if affected else "System-wide"
            
            # 放宽条件：只要有文字内容，就记录下来
            if content:
                current_alerts[str(entity.get('id'))] = {
                    "lines": lines, 
                    "content": content
                }

        current_ids = list(current_alerts.keys())
        print(f"Found {len(current_ids)} valid active alerts after filtering.")

        # 4. Notify NEW alerts
        for aid, info in current_alerts.items():
            if aid not in old_history:
                payload = {
                    "embeds": [{
                        "title": f"🚨 NEW ALERT | Lines: {info['lines']}",
                        "description": info['content'][:4000], # 防止内容超长导致 Discord 报错
                        "color": 15158332
                    }]
                }
                requests.post(WEBHOOK_URL, json=payload)
                print(f"Sent NEW alert notice for ID: {aid}")

        # 5. Notify RESOLVED alerts
        for old_id in old_history:
            if old_id not in current_ids:
                payload = {
                    "embeds": [{
                        "title": "✅ SERVICE RESTORED",
                        "description": f"The alert (ID: {old_id}) has been resolved. Service is resuming.",
                        "color": 3066993
                    }]
                }
                requests.post(WEBHOOK_URL, json=payload)
                print(f"Sent RESTORED notice for ID: {old_id}")

        # 6. Save State
        with open(HISTORY_FILE, 'w') as f:
            json.dump(current_ids, f)

    except Exception as e:
        print(f"Runtime Error: {e}")

if __name__ == "__main__":
    main()
