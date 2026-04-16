import os
import requests
import json
import re

WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
API_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def clean_text(raw_text):
    if not raw_text: return ""
    text = re.sub(r'<br\s*/?>', '\n', raw_text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def extract_mta_text(text_obj):
    if not text_obj: return ""
    translations = text_obj.get('translation', [])
    for t in translations:
        if t.get('language') in ['en', 'en-US', None, '']:
            return clean_text(t.get('text', ''))
    return clean_text(translations[0].get('text', '')) if translations else ""

def main():
    if not WEBHOOK_URL: return

    # 1. 加载历史记录 (支持 list 或 dict 兼容)
    seen_ids = set()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                data = json.load(f)
                seen_ids = set(data) if isinstance(data, list) else set(data.keys())
        except: pass

    # 2. 获取 API 数据
    try:
        data = requests.get(API_URL, timeout=15).json()
    except: return

    entities = data.get('entity', [])
    current_ids = []
    
    for entity in entities:
        alert_id = str(entity.get('id', ''))
        if not alert_id: continue
        current_ids.append(alert_id)

        if alert_id not in seen_ids:
            alert = entity.get('alert', {})
            header = extract_mta_text(alert.get('headerText'))
            desc = extract_mta_text(alert.get('descriptionText'))
            
            # --- 智能分析受影响的对象 ---
            affected_routes = []
            affected_stops = []
            
            for ent in alert.get('informedEntity', []):
                # 抓取线路 (如 L, 7, B103)
                rid = ent.get('routeId')
                if rid and rid not in affected_routes:
                    affected_routes.append(rid)
                
                # 抓取车站/设施 (对于电梯问题至关重要)
                sid = ent.get('stopId')
                if sid and sid not in affected_stops:
                    affected_stops.append(sid)

            # 判定显示类型
            if affected_routes:
                impact_label = f"Lines: {', '.join(affected_routes)}"
            elif affected_stops:
                impact_label = f"Station/Facility: {', '.join(affected_stops)}"
            else:
                impact_label = "System-wide Update"

            # 构造 Discord 消息
            payload = {
                "embeds": [{
                    "title": f"🚨 {header[:250]}" if header else "MTA Status Update",
                    "description": desc[:4000] if desc else "Check MTA website for details.",
                    "color": 16750848, # 橙色，更适合设施/提醒类
                    "fields": [
                        {"name": "Location / Impact", "value": f"**{impact_label}**", "inline": False}
                    ],
                    "footer": {"text": f"Alert ID: {alert_id}"}
                }]
            }

            # 发送 (限制初次频率)
            if len(current_ids) - len(seen_ids) < 15:
                requests.post(WEBHOOK_URL, json=payload)

    # 3. 强制保存为干净的 ID 列表
    with open(HISTORY_FILE, 'w') as f:
        json.dump(current_ids, f)

if __name__ == "__main__":
    main()
