import os
import requests
import json

# 配置
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def get_text_safe(obj):
    """安全提取 MTA 复杂的翻译文本"""
    if not obj or 'translation' not in obj:
        return ""
    translations = obj.get('translation', [])
    if not translations:
        return ""
    # 返回第一个可用的文本
    return translations[0].get('text', '').strip()

def main():
    if not WEBHOOK_URL:
        print("Webhook URL is missing.")
        return

    # 1. 加载历史记录 (强制转换为 Set 提高效率)
    seen_ids = set()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                data = json.load(f)
                seen_ids = set(data) if isinstance(data, list) else set(data.keys())
        except:
            pass

    # 2. 获取 MTA 数据
    try:
        response = requests.get(DATA_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"API Error: {e}")
        return

    entities = data.get('entity', [])
    current_all_ids = []

    for entity in entities:
        alert_id = str(entity.get('id', ''))
        if not alert_id:
            continue
        
        current_all_ids.append(alert_id)

        # 如果是新 ID，不做任何过滤，直接发送原始信息
        if alert_id not in seen_ids:
            alert = entity.get('alert', {})
            
            # 抓取标题和描述
            header = get_text_safe(alert.get('headerText'))
            description = get_text_safe(alert.get('descriptionText'))
            
            # 抓取所有涉及的实体标识符（线路、车站、设施）
            impact_list = []
            for info in alert.get('informedEntity', []):
                # 尝试抓取所有可能的 ID 字段
                tags = []
                for key in ['routeId', 'stopId', 'facilityId', 'agencyId']:
                    val = info.get(key)
                    if val:
                        tags.append(f"{key}: {val}")
                if tags:
                    impact_list.append(" | ".join(tags))
            
            impact_info = "\n".join(impact_list) if impact_list else "No detailed entity ID"

            # 构造 Discord Embed
            payload = {
                "embeds": [{
                    "title": header if header else "MTA Notification",
                    "description": description if description else "No description available.",
                    "color": 15158332, # 红色
                    "fields": [
                        {
                            "name": "Affected Entities (Original Data)",
                            "value": f"
