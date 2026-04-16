import os
import requests
import json

WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def main():
    try:
        res = requests.get(DATA_URL)
        data = res.json()
        entities = data.get('entity', [])
        print(f"Total entities fetched: {len(entities)}")

        with open(HISTORY_FILE, 'r') as f:
            old_history = json.load(f)
            if isinstance(old_history, list): old_history = {} # 彻底清除旧列表格式
    except:
        old_history = {}

    current_alerts = {}
    for ent in entities:
        alert = ent.get('alert')
        if not alert: continue
        
        # 极致提取：不管 MTA 怎么变格式，把能找到的字都抓出来
        h = alert.get('headerText', {}).get('translation', [{}])[0].get('text', '')
        d = alert.get('descriptionText', {}).get('translation', [{}])[0].get('text', '')
        content = f"{h}\n\n{d}".strip()
        
        # 识别线路或设施
        routes = [f"[{e.get('routeId')}]" for e in alert.get('informedEntity', []) if e.get('routeId')]
        title = " ".join(routes) if routes else "🚇 System/Facility Update"
        
        current_alerts[str(ent.get('id'))] = title

        # 核心：如果是新 ID，立刻发 DC
        if str(ent.get('id')) not in old_history:
            payload = {
                "embeds": [{
                    "title": f"📢 NEW | {title}",
                    "description": content[:2000] if content else "No description provided.",
                    "color": 15844367
                }]
            }
            requests.post(WEBHOOK_URL, json=payload)

    # 保存历史
    with open(HISTORY_FILE, 'w') as f:
        json.dump(current_alerts, f)
    print(f"Sync complete. Monitoring {len(current_alerts)} alerts.")

if __name__ == "__main__":
    main()
