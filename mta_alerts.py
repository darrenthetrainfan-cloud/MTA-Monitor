import os
import requests
import json

# Configuration
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def main():
    if not WEBHOOK_URL: return

    try:
        response = requests.get(DATA_URL)
        if response.status_code != 200: return
        data = response.json()
        
        # 1. Load previous alert IDs
        old_history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                old_history = json.load(f)

        # 2. Parse current alerts
        current_alerts = {}
        for entity in data.get('entity', []):
            alert = entity.get('alert')
            if not alert: continue
            
            # Extract Text (Priority: Description > Header)
            desc_obj = alert.get('descriptionText', alert.get('headerText', {}))
            translations = desc_obj.get('translation', [])
            content = translations[0].get('text', '').strip() if translations else ""
            
            # Extract affected lines
            affected = [ent.get('routeId') for ent in alert.get('informedEntity', []) if ent.get('routeId')]
            lines = ", ".join(affected) if affected else "System-wide"
            
            if content and len(content) > 10:
                current_alerts[str(entity.get('id'))] = {"lines": lines, "content": content}

        current_ids = list(current_alerts.keys())

        # 3. Notify NEW Alerts
        for aid, info in current_alerts.items():
            if aid not in old_history:
                payload = {
                    "embeds": [{
                        "title": f"🚨 NEW ALERT | Lines: {info['lines']}",
                        "description": info['content'],
                        "color": 15158332 # Red
                    }]
                }
                requests.post(WEBHOOK_URL, json=payload)

        # 4. Notify RESOLVED Alerts (Service Restoration)
        for old_id in old_history:
            if old_id not in current_ids:
                payload = {
                    "embeds": [{
                        "title": "✅ SERVICE RESTORED",
                        "description": f"The alert (ID: {old_id}) has been removed from the MTA feed. Service on affected lines is resuming.",
                        "color": 3066993 # Green
                    }]
                }
                requests.post(WEBHOOK_URL, json=payload)

        # 5. Save updated history
        with open(HISTORY_FILE, 'w') as f:
            json.dump(current_ids, f)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
