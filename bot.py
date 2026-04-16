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
    # 还原转义字符
    text = html.unescape(text)
    return text.strip()

def get_text_safe(obj):
    """提取文本，如果是空的则返回 None"""
    if not obj: return None
    translations = obj.get('translation', [])
    for trans in translations:
        val = trans.get('text', '')
        cleaned = clean_text(val)
        if cleaned: return cleaned
    return None

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
                # 1. 提取文字内容
                h = get_text_safe(alert.get('headerText'))
                d = get_text_safe(alert.get('descriptionText'))
                
                # --- 重要过滤逻辑 ---
                # 如果标题和描述全是空的，说明这是个无效警报，直接跳过
                if not h and not d:
                    continue 

                # 2. 文本整合：谁有内容就用谁
                final_title = h if h else "MTA Service Update"
                final_desc = d if d else h # 描述空了用标题补，标题空了用描述补
                
                # 3. 识别影响范围
                affected_lines = []
                affected_stations = []
                for ent in alert.get('informedEntity', []):
                    r_id = ent.get('routeId')
                    s_id = ent.get('stopId')
                    # 有些电梯警报会把 ID 藏在这些地方
                    if r_id: affected_lines.append(r_id)
                    if s_id: affected_stations.append(s_id)
                
                if affected_lines:
                    impact = f"🚇 Lines: **{', '.join(set(affected_lines))}**"
                elif affected_stations:
                    impact = f"📍 Station ID: **{', '.join(set(affected_stations))}**"
                else:
                    impact = "🌐 System-wide"

                # 4. 构造 Discord Embed
                payload = {
                    "embeds": [{
                        "title": final_title[:250],
                        "description": final_desc[:2000],
                        "fields": [
                            {"name": "Impact Scope", "value": impact, "inline": False}
                        ],
                        "footer": {"text": f"Alert ID: {alert_id}"},
                        "color": 15844367 if "lmm" in alert_id else 15158332
                    }]
                }
                
                if new_count < 10:
                    res = requests.post(WEBHOOK_URL, json=payload)
                    if res.status_code < 300:
                        new_count += 1

        # 保存记录
        with open(HISTORY_FILE, 'w') as f:
            json.dump(current_ids, f)
        print(f"Done. Sent {new_count} meaningful alerts.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
