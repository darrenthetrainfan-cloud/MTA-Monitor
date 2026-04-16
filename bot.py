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
        print(f"Successfully fetched MTA data. Total entities in API: {len(entities)}")
        
        old_history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    old_history = json.load(f)
            except json.JSONDecodeError:
                old_history = [] 

        current_alerts = {}
        
        for entity in entities:
            alert = entity.get('alert')
            if not alert: 
                continue
                
            # 暴力兼容：抓取所有可能的文字字段
            desc_obj = alert.get('descriptionText') or alert.get('description_text') or {}
            header_obj = alert.get('headerText') or alert.get('header_text') or {}
            
            desc_text = ""
            header_text = ""
            
            # 尝试解包 JSON 结构
            if isinstance(desc_obj, dict) and 'translation' in desc_obj:
                desc_text = desc_obj['translation'][0].get('text', '')
            elif isinstance(desc_obj, str): 
                desc_text = desc_obj
                
            if isinstance(header_obj, dict) and 'translation' in header_obj:
                header_text = header_obj['translation'][0].get('text', '')
            elif isinstance(header_obj, str):
                header_text = header_obj
                
            content = desc_text if desc_text else header_text
            
            # 终极兜底：如果 API 连字都不给，至少我们知道这里有个故障
            if not content:
                content = f"Status Update (No description provided by MTA). Alert ID: {entity.get('id')}"
            
            # 提取线路
            affected = []
            for ent in alert.get('informedEntity', []):
                route_id = ent.get('routeId')
                if route_id and route_id not in affected:
                    affected.append(route_id)
                    
            lines = ", ".join(affected) if affected else "System-wide"
            
            # 现在没有任何条件限制，全部装进去
            current_alerts[str(entity.get('id'))] = {
                "lines": lines, 
                "content": content
            }

        current_ids = list(current_alerts.keys())
        print(f"Found {len(current_ids)} valid active alerts after filtering.")

        # 发送新通知 (最多只发前10个，防止第一次运行把 Discord 搞崩溃)
        notify_count = 0
        for aid, info in current_alerts.items():
            if aid not in old_history:
                if notify_count >= 10:
                    print("Too many new alerts! Stopping notifications for this run to avoid Discord rate limits.")
                    break
                
                payload = {
                    "embeds": [{
                        "title": f"🚨 NEW ALERT | Lines: {info['lines']}",
                        "description": info['content'][:4000], 
                        "color": 15158332
                    }]
                }
                requests.post(WEBHOOK_URL, json=payload)
                print(f"Sent NEW alert notice for ID: {aid}")
                notify_count += 1

        # 更新历史记录
        with open(HISTORY_FILE, 'w') as f:
            json.dump(current_ids, f)

    except Exception as e:
        print(f"Runtime Error: {e}")

if __name__ == "__main__":
    main()
