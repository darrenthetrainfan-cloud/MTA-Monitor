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
        response = requests.get(DATA_URL)
        if response.status_code != 200:
            print(f"Failed to fetch MTA data: {response.status_code}")
            return
        
        data = response.json()
        print("Successfully fetched MTA data.")
        
        old_history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                old_history = json.load(f)

        current_alerts = {}
        for entity in data.get('entity', []):
            alert = entity.get('alert')
            if not alert: continue
            
            # Content extraction
            desc_obj = alert.get('descriptionText', alert.get('headerText', {}))
            translations = desc_obj.get('translation', [])
            content = translations[0].get('text', '').strip() if translations else ""
            
            # Line extraction
            affected = [ent.get('routeId') for ent in alert.get('informedEntity', []) if ent.get('routeId')]
            lines = ", ".join(affected) if affected else "System"
            
            if content and len(content) > 10:
                current_alerts[str(entity.get('id'))] = {"lines": lines, "content": content}

        current_ids = list(current_alerts.keys())
        print(f"Found {len(current_ids)} active alerts.")

        # Check for NEW alerts
        for aid, info in current_alerts.items():
            if aid not in old_history:
                payload = {
                    "embeds": [{
                        "title": f"🚨 NEW ALERT | Lines: {info['lines']}",
                        "description": info['content'],
                        "color": 15158332
                    }]
                }
                requests.post(WEBHOOK_URL, json=payload)
                print(f"Sent notification for alert {aid}")

        # Check for RESOLVED alerts
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
                print(f"Sent restoration notice for {old_id}")

        with open(HISTORY_FILE, 'w') as f:
            json.dump(current_ids, f)

    except Exception as e:
        print(f"Runtime Error: {e}")

if __name__ == "__main__":
    main()
