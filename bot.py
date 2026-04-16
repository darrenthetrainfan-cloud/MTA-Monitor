import os
import requests
import json
import re
import html

# 配置
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def clean_text(raw_html):
    """深度清理 HTML 并处理换行"""
    if not raw_html: return ""
    # 替换 <br> 为换行
    text = re.sub(r'<br\s*/?>', '\n', raw_html, flags=re.IGNORECASE)
    # 移除所有 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    # 还原转义字符 (&amp; 等)
    text = html.unescape(text)
    # 移除多余空格和重复换行
    text = re.sub(r'\n\s*\n', '\n', text)
    return text.strip()

def get_text_safe(obj):
    """从翻译对象中提取文本，确保不返回空字符串"""
    if not obj: return ""
    translations = obj.get('translation', [])
    for trans in translations:
        val = trans.get('text', '')
        if val: return clean_text(val)
    return ""

def main():
    if not WEBHOOK_URL: return

    try:
        response = requests.get(DATA_URL, timeout=15)
        if response.status_code != 200: return
        
        entities = response.json().get('entity', [])
        
        # 加载历史
        try:
            with open(HISTORY_FILE, 'r') as f:
                old_history = json.load(f)
                if isinstance(old_history, dict): old_history = list(old_history.keys())
        except:
            old_history = []

        current_ids = []
        new_count = 0

        for entity in entities:
            alert = entity.get('alert')
            if not alert: continue
            
            alert_id = str(entity.get('id'))
            current_ids.append(alert_id)
                
            if alert_id not in old_history:
                # 提取标题和描述
                h = get_text_safe(alert.get('headerText'))
                d = get_text_safe(alert.get('descriptionText'))
                
                # --- 智能补全逻辑 ---
                # 如果描述为空，就把标题当作描述；如果标题为空，就用描述
                final_title = h if h else "MTA Service Alert"
                final_desc = d if d else h
                if not final_desc: final_desc = "No specific details provided."

                # --- 智能识别影响范围 ---
                affected_lines = []
                affected_stations = []
                for ent in alert.get('informedEntity', []):
                    r_id = ent.get('routeId')
                    s_id = ent.get('stopId')
                    if r_id and r_id not in affected_lines: affected_lines.append(r_id)
                    if s_id and s_id not in affected_stations: affected_stations.append(s_id)
                
                if affected_lines:
                    impact = f"🚇 Lines: **{', '.join(affected_lines)}**"
                elif affected_stations:
                    # 如果是电梯，通常这里会显示车站 ID
                    impact = f"📍 Station/Facility: **{', '.join(affected_stations)}**"
                else:
                    impact = "🌐 System-wide"

                # 构造 Discord Embed
                payload = {
                    "embeds": [{
                        "title": (final_title[:250] + '...') if len(final_title) > 250 else final_title,
                        "description": final_desc[:2000],
                        "fields": [
                            {"name": "Impact Scope", "value": impact, "inline": False}
                        ],
                        "footer": {"text": f"ID: {alert_id}"},
                        "color": 15844367 if "lmm" in alert_id else 15158332 # 电梯黄色，其他红色
                    }]
                }
                
                if new_count < 10:
                    if requests.post(WEBHOOK_URL, json=payload).status_code < 300:
                        new_count += 1

        with open(HISTORY_FILE, 'w') as f:
            json.dump(current_ids, f)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
