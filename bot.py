import os
import requests
import json

WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
# 这个 URL 包含了 MTA 所有的 Alert 数据（Subway, Bus, LIRR, MNR）
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def get_text(obj):
    """通用文字提取工具，适配不同类型的 API 格式"""
    if not obj: return ""
    if isinstance(obj, str): return obj
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
            
            # 合并文本内容
            full_body = f"{header}\n\n{desc}" if header and desc and header != desc else (header or desc)
            if not full_body: continue

            # 线路识别（全类型适配）
            affected = []
            agency_ids = set()
            for ent in alert.get('informedEntity', []):
                # 尝试抓取各种 ID
                route = ent.get('routeId')
                agency = ent.get('agencyId')
                if route: affected.append(route)
                if agency: agency_ids.add(agency)
            
            # 格式化线路显示，例如 [7] [Q] 或 [MTA NYCT]
            if affected:
                lines_str = " ".join([f"[{r}]" for r in sorted(list(set(affected)))])
            elif agency_ids:
                lines_str = f"🌐 Agency: {'/'.join(agency_ids)}"
            else:
                lines_str = "🚇 System Wide"

            current_alerts[str(entity.get('id'))] = {
                "lines": lines_str,
                "body": full_body
            }

        # 1. 发送新警报 (包含所有类型)
        new_count = 0
        for aid, info in current_alerts.items():
            if aid not in old_history:
                if new_count >= 15: break # 第一次运行可能会很多，之后就稳定了
                
                payload = {
                    "embeds": [{
                        "title": f"📢 MTA ALL-TYPE | {info['lines']}",
                        "description": info['body'][:4000],
                        "color": 15844367, # 金色，代表全类型监控
                    }]
                }
                requests.post(WEBHOOK_URL, json=payload)
                new_count += 1

        # 2. 发送恢复通知
        res_count = 0
        for old_id, old_lines in old_history.items():
            if old_id not in current_alerts:
                if res_count >= 10: break
                payload = {
                    "embeds": [{
                        "title": f"✅ RESOLVED | {old_lines}",
                        "description": "This service alert/update is no longer active.",
                        "color": 3066993,
                    }]
                }
                requests.post(WEBHOOK_URL, json=payload)
                res_count += 1

        # 保存历史
        new_history = {aid: info['lines'] for aid, info in current_alerts.items()}
        with open(HISTORY_FILE, 'w') as f:
            json.dump(new_history, f)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
