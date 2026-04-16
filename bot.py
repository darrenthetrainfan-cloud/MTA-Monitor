import os
import requests
import json
import re
import html

WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def clean_html(raw_html):
    """清理文本中的 HTML 标签并处理换行"""
    if not raw_html:
        return ""
    # 1. 将 <br> 或 <br/> 替换为换行符 \n，保证 Discord 里能正确换行
    text = re.sub(r'<br\s*/?>', '\n', raw_html, flags=re.IGNORECASE)
    # 2. 移除所有其他 HTML 标签 (例如 <span>, <strong> 等)
    text = re.sub(r'<[^>]+>', '', text)
    # 3. 将 HTML 实体（如 &amp;, &nbsp;）还原为普通字符
    text = html.unescape(text)
    return text.strip()

def get_text(obj):
    if not obj: return ""
    translations = obj.get('translation', [])
    if translations:
        raw_text = translations[0].get('text', '')
        return clean_html(raw_text) # 在这里调用清理函数
    return ""

def main():
    if not WEBHOOK_URL: return

    try:
        response = requests.get(DATA_URL)
        if response.status_code != 200: return
        
        data = response.json()
        entities = data.get('entity', [])
        
        # 加载历史记录
        old_history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    data_load = json.load(f)
                    # 兼容性处理：如果是字典则取 key，如果是列表则直接用
                    old_history = list(data_load.keys()) if isinstance(data_load, dict) else data_load
            except:
                old_history = [] 

        current_ids = []
        new_count = 0

        for entity in entities:
            alert = entity.get('alert')
            if not alert: continue
            
            alert_id = str(entity.get('id'))
            current_ids.append(alert_id)
                
            # 如果是新警报
            if alert_id not in old_history:
                header = get_text(alert.get('headerText'))
                desc = get_text(alert.get('descriptionText'))
                
                # 提取受影响线路
                affected = []
                for ent in alert.get('informedEntity', []):
                    rid = ent.get('routeId')
                    if rid and rid not in affected:
                        affected.append(rid)
                
                lines_str = ", ".join(affected) if affected else "System-wide"
                
                # 构造 Discord Embed
                payload = {
                    "embeds": [{
                        "title": header if header else "MTA Alert",
                        "description": desc if desc else "No details provided.",
                        "fields": [
                            {"name": "Affected Lines", "value": f"**{lines_str}**", "inline": False}
                        ],
                        "footer": {"text": f"Alert ID: {alert_id}"},
                        "color": 15158332 # 红色
                    }]
                }
                
                if new_count < 10: # 限制单次发送数量防止刷屏
                    requests.post(WEBHOOK_URL, json=payload)
                    new_count += 1

        # 保存当前所有 ID 到历史记录
        with open(HISTORY_FILE, 'w') as f:
            json.dump(current_ids, f)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
