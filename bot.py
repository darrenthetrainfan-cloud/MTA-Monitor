import os
import requests
import json

# 环境配置
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
# 使用全量 JSON 数据源
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def get_text(obj):
    """最原始的文本提取"""
    if not obj or 'translation' not in obj:
        return ""
    trans = obj.get('translation', [])
    return trans[0].get('text', '').strip() if trans else ""

def main():
    if not WEBHOOK_URL:
        print("WEBHOOK_URL is missing")
        return

    # 1. 安全读取历史
    seen_ids = set()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                raw = json.load(f)
                # 兼容旧的字典格式或列表格式
                seen_ids = set(raw) if isinstance(raw, list) else set(raw.keys())
        except:
            pass

    # 2. 获取 API 数据
    try:
        resp = requests.get(DATA_URL, timeout=30)
        data = resp.json()
    except Exception as e:
        print(f"API Error: {e}")
        return

    entities = data.get('entity', [])
    current_ids = []

    for entity in entities:
        alert_id = str(entity.get('id', ''))
        if not alert_id: continue
        
        current_ids.append(alert_id)

        # 只要是新 ID 就发送
        if alert_id not in seen_ids:
            alert = entity.get('alert', {})
            
            # 抓取标题、描述
            header = get_text(alert.get('headerText'))
            desc = get_text(alert.get('descriptionText'))
            
            # 抓取所有 ID 标识（线路、车站、设施）
            impact_details = []
            for info in alert.get('informedEntity', []):
                # 将 info 字典里所有的键值对转成文字，不漏掉任何字段
                tags = [f"{k}: {v}" for k, v in info.items() if v]
                if tags:
                    impact_details.append(" | ".join(tags))
            
            entity_box = "\n".join(impact_details) if impact_details else "No Entity IDs"

            # 组装 Discord 消息
            payload = {
                "embeds": [{
                    "title": header if header else f"MTA Alert {alert_id}",
                    "description": desc if desc else "Check MTA website for details.",
                    "color": 3447003,
                    "fields": [
                        {
                            "name": "Raw Data Entities",
                            "value": f"
http://googleusercontent.com/immersive_entry_chip/0

### ⚠️ 操作提醒
代码保存后，请去 GitHub 仓库把 `alert_history.json` 的内容手动清空并改为 `[]`。这样能重置你的历史记录，让脚本重新扫描一次当前所有的活跃警报，包括你之前看不到的电梯详情。
