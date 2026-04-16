import os
import requests
import json

WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json" # 保持文件名不变，防止你的 GitHub Action 报错

def get_text(text_obj):
    """安全提取多语言文本中的英语内容"""
    if not text_obj: return ""
    translations = text_obj.get('translation', [])
    if not translations: return ""
    return translations[0].get('text', '').strip()

def main():
    if not WEBHOOK_URL:
        print("Webhook URL is missing!")
        return

    # 1. 极简读取历史记录：强制转换为单纯的 ID 列表
    seen_ids = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                data = json.load(f)
                # 不管以前存的是字典还是列表，暴力提取出 ID
                if isinstance(data, dict):
                    seen_ids = list(data.keys())
                elif isinstance(data, list):
                    seen_ids = data
        except Exception:
            seen_ids = []

    # 2. 获取 MTA 最新数据
    try:
        response = requests.get(DATA_URL, timeout=15)
        response.raise_for_status() # 如果网络错误直接跳到 except
        data = response.json()
    except Exception as e:
        print(f"Failed to fetch MTA API: {e}")
        return

    entities = data.get('entity', [])
    current_ids = []
    new_alerts_to_send = []

    # 3. 解析警报数据
    for entity in entities:
        alert_id = str(entity.get('id', ''))
        if not alert_id: continue
        
        current_ids.append(alert_id)

        # 如果这个警报以前没见过，就加入待发送列表
        if alert_id not in seen_ids:
            alert = entity.get('alert', {})
            
            # 提取文本
            header = get_text(alert.get('headerText'))
            desc = get_text(alert.get('descriptionText'))
            
            # 智能清理：如果数据源的描述里包含了多余的重复标题，自动删掉
            if desc.startswith(header) and len(header) > 0:
                desc = desc[len(header):].strip()

            # 提取线路
            affected_lines = []
            for ent in alert.get('informedEntity', []):
                route_id = ent.get('routeId')
                if route_id and route_id not in affected_lines:
                    affected_lines.append(route_id)
            
            # 格式化线路文本
            lines_str = ", ".join(affected_lines) if affected_lines else "System-wide / Facilities"
            
            # 防止空标题导致 Discord 拒绝接收
            display_title = header if header else "MTA Service Update"
            display_desc = desc if desc else "No details provided."

            new_alerts_to_send.append({
                "id": alert_id,
                "title": display_title,
                "desc": display_desc,
                "lines": lines_str
            })

    # 4. 推送到 Discord
    sent_count = 0
    for alert in new_alerts_to_send:
        if sent_count >= 10: break # 防止初次运行或大面积故障时刷屏

        payload = {
            "embeds": [{
                "title": alert["title"][:256], # Discord 标题字数限制
                "description": alert["desc"][:4000], # Discord 描述字数限制
                "color": 15158332, # 红色
                "fields": [
                    {
                        "name": "Affected Lines",
                        "value": f"**{alert['lines']}**",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": f"Alert ID: {alert['id']}"
                }
            }]
        }

        try:
            requests.post(WEBHOOK_URL, json=payload)
            sent_count += 1
        except Exception as e:
            print(f"Discord Post Error: {e}")

    # 5. 覆盖保存当前的 ID 列表（纯净的 List 格式）
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(current_ids, f)
        print(f"Successfully tracked {len(current_ids)} active alerts. Sent {sent_count} new alerts.")
    except Exception as e:
        print(f"File Save Error: {e}")

if __name__ == "__main__":
    main()
