import os
import requests
import json

WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
# 全量 JSON 数据源，包含地铁、巴士、电梯、闸机等所有警报
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def get_all_text(text_obj):
    """提取所有可用的翻译文本，不留死角"""
    if not text_obj or 'translation' not in text_obj:
        return ""
    # 将所有语言的文本拼接起来（通常只有英文，但这样最保险）
    texts = [t.get('text', '').strip() for t in text_obj.get('translation', []) if t.get('text')]
    return "\n".join(texts)

def main():
    if not WEBHOOK_URL:
        print("Webhook URL missing.")
        return

    # 1. 加载历史记录 (强制转换为最简单的 ID 列表)
    seen_ids = set()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                raw = json.load(f)
                seen_ids = set(raw) if isinstance(raw, list) else set(raw.keys())
        except:
            pass

    # 2. 获取原始数据
    try:
        response = requests.get(DATA_URL, timeout=30)
        data = response.json()
    except Exception as e:
        print(f"API Error: {e}")
        return

    entities = data.get('entity', [])
    current_ids = []

    for entity in entities:
        alert_id = str(entity.get('id', ''))
        if not alert_id: continue
        
        current_ids.append(alert_id)

        # 只要是新 ID，不做任何过滤，直接发送
        if alert_id not in seen_ids:
            alert = entity.get('alert', {})
            
            # 原始字段全抓取
            header = get_all_text(alert.get('headerText'))
            description = get_all_text(alert.get('descriptionText'))
            
            # 抓取所有涉及的实体（Route, Stop, Agency 等）
            impacted = []
            for info in alert.get('informedEntity', []):
                # 收集所有可能的标识符
                parts = [str(info.get(k)) for k in ['routeId', 'stopId', 'agencyId', 'facilityId'] if info.get(k)]
                if parts:
                    impacted.append(" / ".join(parts))
            
            impact_str = " | ".join(impacted) if impacted else "No specific location data"

            # 组装 Discord Embed
            payload = {
                "embeds": [{
                    "title": header if header else f"MTA Alert {alert_id}",
                    "description": description if description else "No description text provided in source.",
                    "color": 3447003, # 蓝色
                    "fields": [
                        {
                            "name": "Source Informed Entities (ID/Route/Stop)",
                            "value": f"
http://googleusercontent.com/immersive_entry_chip/0

### 🧱 为什么这次能解决问题？
1.  **取消所有 `if not` 过滤**：之前的代码会因为“没描述”或“标题太短”直接跳过。现在哪怕 MTA 只发了一个 ID，代码也会强行把这个 ID 发到 Discord。
2.  **全维度实体抓取**：我增加了对 `facilityId` 和 `agencyId` 的抓取。电梯问题通常就在这些字段里，现在的代码会将它们全部列在 `Source Informed Entities` 这一栏。
3.  **原始文本呈现**：使用了 ` 
http://googleusercontent.com/immersive_entry_chip/1
