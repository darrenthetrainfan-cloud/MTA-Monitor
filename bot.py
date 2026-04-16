import os
import requests
import json

# 配置：从 GitHub Secrets 读取 Discord Webhook
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

# 使用你提供的四个 JSON 格式 API 源
SOURCES = {
    "Subway": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts.json",
    "Bus": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fbus-alerts.json",
    "LIRR": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Flirr-alerts.json",
    "MNR": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fmnr-alerts.json"
}
HISTORY_FILE = "alert_history.json"

def get_text_safe(obj):
    """安全提取翻译列表中的文本，防止字段缺失导致报错"""
    if not obj or 'translation' not in obj:
        return ""
    translations = obj.get('translation', [])
    # 优先返回第一条内容（通常是英文）
    return translations[0].get('text', '').strip() if translations else ""

def main():
    if not WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL is not set.")
        return

    # 1. 加载历史记录 (修正了导致 'list' object has no attribute 'items' 的解析逻辑)
    seen_ids = set()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                data = json.load(f)
                # 兼容旧版本的字典格式和现在的列表格式
                if isinstance(data, list):
                    seen_ids = set(data)
                elif isinstance(data, dict):
                    seen_ids = set(data.keys())
        except Exception as e:
            print(f"Warning: Could not load history, starting fresh. {e}")

    new_history = []
    
    # 2. 依次抓取四个数据源
    for mode, url in SOURCES.items():
        print(f"Checking {mode} alerts...")
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            # 此时 r.json() 会成功，因为 URL 已更新为 .json 后缀
            feed_data = r.json()
            entities = feed_data.get('entity', [])
        except Exception as e:
            print(f"Skip {mode} due to fetch error: {e}")
            continue

        for entity in entities:
            alert_id = str(entity.get('id', ''))
            if not alert_id: continue
            
            new_history.append(alert_id)

            # 3. 如果是从未见过的警报，立即推送
            if alert_id not in seen_ids:
                alert = entity.get('alert', {})
                header = get_text_safe(alert.get('headerText'))
                description = get_text_safe(alert.get('descriptionText'))
                
                # 提取受影响的实体信息 (专门针对电梯/设施 ID 优化)
                impact_details = []
                for info in alert.get('informedEntity', []):
                    # 动态抓取 info 中所有存在的 ID 字段 (routeId, stopId, facilityId 等)
                    tags = [f"{k}: {v}" for k, v in info.items() if v]
                    if tags:
                        impact_details.append(" | ".join(tags))
                
                impact_str = "\n".join(impact_details) if impact_details else "General System Update"

                # 构造 Discord Embed
                payload = {
                    "embeds": [{
