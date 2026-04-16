import os
import requests
import json
import re
import html

# 配置信息
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def clean_html(raw_html):
    """清理文本中的 HTML 标签并处理换行"""
    if not raw_html:
        return ""
    # 1. 处理换行符
    text = re.sub(r'<br\s*/?>', '\n', raw_html, flags=re.IGNORECASE)
    # 2. 移除所有 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    # 3. 还原 HTML 实体符号 (比如 &amp; -> &)
    text = html.unescape(text)
    return text.strip()

def get_text(obj):
    """从 MTA 的翻译对象中提取并清理文本"""
    if not obj: 
        return ""
    translations = obj.get('translation', [])
    if translations:
        # 优先提取文本并进行清洗
        raw_val = translations[0].get('text', '')
        return clean_html(raw_val)
    return ""

def main():
    if not WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL not set.")
        return

    try:
        # 获取数据
        response = requests.get(DATA_URL, timeout=15)
        if response.status_code != 200:
            print(f"API Error: {response.status_code}")
            return
        
        data = response.json()
        entities = data.get('entity', [])
        
        # 加载历史记录
        old_history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    data_load = json.load(f)
                    # 兼容处理：支持列表或字典格式
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
                raw_header = get_text(alert.get('headerText'))
                raw_desc = get_text(alert.get('descriptionText'))
                
                # --- 文本优化策略 ---
                # 如果描述为空（常见于电梯故障），用标题代替描述
                # 如果标题为空，用描述代替标题
                display_title = raw_header if raw_header else "MTA Service Alert"
                display_desc = raw_desc if raw_desc else raw_header
                
                if not display_desc: # 万一两个都空
                    display_desc = "No detailed information provided by MTA."

                # --- 受影响范围识别 (线路 vs 车站) ---
                affected_routes = []
                affected_stops = []
                for ent in alert.get('informedEntity', []):
                    rid = ent.get('routeId')
                    sid = ent.get('stopId')
                    if rid and rid not in affected_routes:
                        affected_routes.append(rid)
                    if sid and sid not in affected_stops:
                        affected_stops.append(sid)
                
                if affected_routes:
                    scope_str = f"Lines: **{', '.join(affected_routes)}**"
                elif affected_stops:
                    scope_str = f"Stops: **{', '.join(affected_stops)}**"
                else:
                    scope_str = "System-wide / General Information"

                # --- 构造 Discord Embed ---
                # 限制标题长度防止报错 (Discord limit 256)
                final_title = (display_title[:250] + '...') if len(display_title) > 250 else display_title
                
                payload = {
                    "embeds": [{
                        "title": final_title,
                        "description": display_desc[:2000], # Discord limit 4096
                        "fields": [
                            {"name": "Affected Scope", "value": scope_str, "inline": False}
                        ],
                        "footer": {"text": f"Alert ID: {alert_id}"},
                        "color": 15158332 # 红色
                    }]
                }
                
                # 频率控制：单次运行最多发 10 条，避免被 Discord 封禁
                if new_count < 10:
                    resp = requests.post(WEBHOOK_URL, json=payload)
                    if resp.status_code == 204:
                        new_count += 1
                    else:
                        print(f"Failed to send {alert_id}: {resp.status_code}")

        # 保存当前所有 ID 到历史记录（覆盖旧记录）
        with open(HISTORY_FILE, 'w') as f:
            json.dump(current_ids, f)
            
        print(f"Task finished. Sent {new_count} new alerts.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
