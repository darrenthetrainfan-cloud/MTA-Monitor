import os
import requests
import json

WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def main():
    if not WEBHOOK_URL:
        print("Error: Webhook URL is missing!")
        return

    try:
        response = requests.get(DATA_URL)
        if response.status_code != 200:
            return
        
        data = response.json()
        entities = data.get('entity', [])
        
        old_history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    old_history = json.load(f)
            except:
                old_history = [] 

        current_alerts = {}
        for entity in entities:
            alert = entity.get('alert')
            if not alert: continue
                
            # 提取标题和描述
            h_obj = alert.get('headerText', {})
            d_obj = alert.get('descriptionText', {})
            header = h_obj.get('translation', [{}])[0].get('text', 'Alert Update').strip()
            desc = d_obj.get('translation', [{}])[0].get('text', '').strip()
            
            # 提取线路并格式化为 [L], [1]
            affected = []
            for ent in alert.get('informedEntity', []):
                rid = ent.get('routeId')
                if rid and rid not in affected:
                    affected.append(f"[{rid}]")
            
            lines_str = " ".join(affected) if affected else "🚇 System-wide"
            
            current_alerts[str(entity.get('id'))] = {
                "lines": lines_str,
                "header": header,
                "desc": desc
            }

        current_ids = list(current_alerts.keys())

        # --- 发送新警报 (红色) ---
        new_count = 0
        for aid, info in current_alerts.items():
            if aid not in old_history:
                if new_count >= 8: break # 限制单次发送数量

                # 拼接显示内容：如果描述和标题一样，就只显示一个
                full_body = f"**{info['header']}**\n\n{info['desc']}" if info['desc'] and info['desc'] != info['header'] else info['header']
                
                payload = {
                    "embeds": [{
                        "title": f"🚨 MTA ALERT | {info['lines']}",
                        "description": full_body[:2000],
                        "color": 15158332, # 红色
                        "footer": {"text": f"Alert ID: {aid}"}
                    }]
                }
                requests.post(WEBHOOK_URL, json=payload)
                new_count += 1

        # --- 发送恢复通知 (绿色) ---
        # 如果你不需要恢复通知，可以把下面这段删掉
        res_count = 0
        for old_id in old_history:
            if old_id not in current_ids:
                if res_count >= 5: break
                payload = {
                    "embeds": [{
                        "title": "✅ SERVICE RESTORED",
                        "description": f"The alert (ID: {old_id}) is no longer active. Service is resuming normal operations.",
                        "color": 3066993, # 绿色
                    }]
                }
                requests.post(WEBHOOK_URL, json=payload)
                res_count += 1

        with open(HISTORY_FILE, 'w') as f:
            json.dump(current_ids, f)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
