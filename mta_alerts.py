import os
import requests
import json
import time

# --- Configuration ---
WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def main():
    if not WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL environment variable is missing.")
        return

    print("Fetching data from MTA API...")
    
    try:
        response = requests.get(DATA_URL, timeout=15)
        if response.status_code != 200:
            print(f"Error: MTA API returned status code {response.status_code}")
            return
            
        data = response.json()
        
        # 1. Load previous alerts (Now loading as a dictionary)
        old_history = {}
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    old_history = json.load(f)
            except json.JSONDecodeError:
                print("Warning: History file is corrupted. Starting fresh.")

        # 2. Parse current alerts
        current_alerts = {}
        for entity in data.get('entity', []):
            alert = entity.get('alert')
            if not alert: 
                continue
            
            # Extract Text (Priority: Description > Header)
            desc_obj = alert.get('descriptionText', alert.get('headerText', {}))
            translations = desc_obj.get('translation', [])
            content = translations[0].get('text', '').strip() if translations else ""
            
            # Extract affected lines
            affected = [ent.get('routeId') for ent in alert.get('informedEntity', []) if ent.get('routeId')]
            # Remove duplicates and format
            lines = ", ".join(sorted(set(affected))) if affected else "System-wide"
            
            if content and len(content) > 5:
                current_alerts[str(entity.get('id'))] = {
                    "lines": lines, 
                    "content": content
                }

        print(f"Found {len(current_alerts)} active alerts in the feed.")

        # 3. Categorize New and Resolved Alerts
        new_alerts = {k: v for k, v in current_alerts.items() if k not in old_history}
        resolved_alerts = {k: v for k, v in old_history.items() if k not in current_alerts}

        print(f"New alerts to broadcast: {len(new_alerts)}")
        print(f"Resolved alerts to broadcast: {len(resolved_alerts)}")

        # --- Anti-Spam Protection ---
        # If there are too many new alerts (usually happens on the very first run), 
        # we skip sending to Discord to prevent your webhook from getting banned.
        if len(new_alerts) > 15 and not old_history:
            print("First run detected. Skipping Discord notifications to prevent spam. Saving history...")
        else:
            # 4. Send NEW Alerts
            for aid, info in new_alerts.items():
                desc = info['content']
                if len(desc) > 2000: 
                    desc = desc[:2000] + "...\n*[Truncated]*"
                
                payload = {
                    "embeds": [{
                        "title": f"🚨 NEW ALERT | Lines: {info['lines']}",
                        "description": desc,
                        "color": 15158332, # Red
                        "footer": {"text": f"Alert ID: {aid}"}
                    }]
                }
                post_to_discord(payload)

            # 5. Send RESOLVED Alerts
            for old_id, old_info in resolved_alerts.items():
                payload = {
                    "embeds": [{
                        "title": f"✅ SERVICE RESTORED | Lines: {old_info['lines']}",
                        "description": f"The previous issue affecting the **{old_info['lines']}** line(s) has been resolved.",
                        "color": 3066993, # Green
                        "footer": {"text": f"Resolved Alert ID: {old_id}"}
                    }]
                }
                post_to_discord(payload)

        # 6. Save updated history
        with open(HISTORY_FILE, 'w') as f:
            json.dump(current_alerts, f)
        print("Alert history successfully updated.")

    except Exception as e:
        print(f"A critical error occurred: {e}")

def post_to_discord(payload):
    """Helper function to safely post to Discord with rate-limit protection."""
    try:
        r = requests.post(WEBHOOK_URL, json=payload)
        if r.status_code not in (200, 204):
            print(f"Discord API Error [{r.status_code}]: {r.text}")
        else:
            print(f"Successfully pushed to Discord: {payload['embeds'][0]['title']}")
        # Mandatory sleep to prevent Discord from blocking the Webhook
        time.sleep(1.5) 
    except Exception as e:
        print(f"Failed to connect to Discord Webhook: {e}")

if __name__ == "__main__":
    main()
