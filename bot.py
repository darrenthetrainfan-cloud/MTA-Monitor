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
        
        old_history_data = {} # 存储 ID 到线路名的映射
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    # 读取旧的历史字典
                    old_history_data = json.load(f)
            except:
                old_history_data = {} 

        current_alerts = {}
        for entity in entities:
            alert = entity.get('alert')
            if not alert: continue
                
            # 提取标题和描述
            h_obj = alert.get('headerText', {})
            d_obj = alert.get('descriptionText', {})
            header = h_obj.get('translation', [{}])[0].get('text', '').strip()
            desc = d_obj.get('translation', [{}])[0].get('text', '').strip()
            
            # 合并文字
            if header and desc and header != desc:
                full_text = f"{header}\n\n{desc}"
            else:
                full_text = header if header else desc
            
            # 提取线路 [A] [C]
            affected = []
            for ent in alert.get('informedEntity', []):
                rid = ent.get('routeId')
                if rid and rid not in affected:
                    affected.append(f"[{rid}]")
            
            lines_str = " ".join(affected) if affected else "🚇 System Update"
            
            current_alerts[str(entity.get('id'))] = {
                "lines": lines_str,
                "body": full_text
            }

        # --- 1. 发送新警报 (红色) ---
        new_count = 0
        for aid, info in current_alerts.items():
            if aid not in old_history_data:
                if new_count >= 10: break
                payload = {
                    "embeds": [{
                        "title": f"🚨 NEW: {info['lines']}",
                        "description": info['body'][:4000],
                        "color": 15158332,
                    }]
                }
                requests.post(WEBHOOK_URL, json=payload)
                new_count += 1

        # --- 2. 发送恢复通知 (绿色) ---
        res_count = 0
        for old_id, old_lines in old_history_data.items():
            if old_id not in current_alerts:
                if res_count >= 5: break
                payload = {
                    "embeds": [{
                        "title": f"✅ RESTORED: {old_lines}",
                        "description": f"The service alert (ID: {old_id}) has been resolved. Service is resuming normal operations.",
                        "color": 3066993,
                    }]
                }
                requests.post(WEBHOOK_URL, json=payload)
                res_count += 1

        # --- 3. 保存历史 (保存 ID 和线路名，方便恢复时显示) ---
        new_history_to_save = {aid: info['lines'] for aid, info in current_alerts.items()}
        with open(HISTORY_FILE, 'w') as f:
            json.dump(new_history_to_save, f)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
