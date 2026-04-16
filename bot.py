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
        
        old_history = {}
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    old_history = json.load(f)
            except:
                old_history = {} 

        current_alerts = {}
        for entity in entities:
            alert = entity.get('alert')
            if not alert: continue
                
            header = get_text(alert.get('headerText'))
            desc = get_text(alert.get('descriptionText'))
            full_body = f"{header}\n\n{desc}" if header and desc and header != desc else (header or desc)
            if not full_body: continue

            # 智能分类标签
            tags = []
            lower_body = full_body.lower()
            if "elevator" in lower_body: tags.append("🛗 ELEVATOR")
            if "escalator" in lower_body: tags.append("🪜 ESCALATOR")
            if any(x in lower_body for x in ["gate", "turnstile", "fare", "omny"]): tags.append("💳 FARE/GATE")

            # 线路与车站识别
            affected_routes = []
            affected_stops = []
            for ent in alert.get('informedEntity', []):
                r_id = ent.get('routeId')
                s_id = ent.get('stopId')
                if r_id and r_id not in affected_routes: affected_routes.append(f"[{r_id}]")
                if s_id and s_id not in affected_stops: affected_stops.append(s_id)
            
            # 构建标题
            prefix = " | ".join(tags) if tags else "🚇 SERVICE"
            if affected_routes:
                location = " ".join(affected_routes)
            elif affected_stops:
                location = f"Station: {affected_stops[0]}"
            else:
                location = "System Update"

            current_alerts[str(entity.get('id'))] = {
                "title": f"{prefix} | {location}",
                "body": full_body
            }

        # 1. 发送通知
        new_count = 0
        for aid, info in current_alerts.items():
            if aid not in old_history:
                if new_count >= 15: break 
                
                payload = {
                    "embeds": [{
                        "title": info['title'],
                        "description": info['body'][:4000],
                        "color": 15844367 if "🚇" in info['title'] else 3447003, # 蓝色代表设施，金色代表运营
                    }]
                }
                requests.post(WEBHOOK_URL, json=payload)
                new_count += 1

        # 2. 恢复通知
        res_count = 0
        for old_id, old_title in old_history.items():
            if old_id not in current_alerts:
                if res_count >= 10: break
                requests.post(WEBHOOK_URL, json={
                    "embeds": [{
                        "title": f"✅ RESOLVED: {old_title}",
                        "color": 3066993,
                    }]
                })
                res_count += 1

        # 3. 保存
        new_history = {aid: info['title'] for aid, info in current_alerts.items()}
        with open(HISTORY_FILE, 'w') as f:
            json.dump(new_history, f)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
