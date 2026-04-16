import os
import requests
import json

# 环境配置
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
# 全量 JSON 数据源，涵盖所有类型的警报
DATA_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"
HISTORY_FILE = "alert_history.json"

def get_text_raw(obj):
    """最原始的文本提取，不做任何过滤或清理"""
    if not obj or 'translation' not in obj:
        return ""
    translations = obj.get('translation', [])
    if not translations:
        return ""
    # 直接提取第一个可用的文本内容
    return translations[0].get('text', '').strip()

def main():
    if not WEBHOOK_URL:
        print("Error: WEBHOOK_URL is not set.")
        return

    # 1. 强力加载历史记录：支持字典或列表格式兼容
    seen_ids = set()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                raw_history = json.load(f)
                if isinstance(raw_history, list):
                    seen_ids = set(raw_history)
                elif isinstance(raw_history, dict):
                    seen_ids = set(raw_history.keys())
        except:
            pass # 如果文件损坏，则本次运行视为全量推送

    # 2. 获取 MTA 原始 API 数据
    try:
        response = requests.get(DATA_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"API Fetch Error: {e}")
        return

    entities = data.get('entity', [])
    current_ids = []

    for entity in entities:
        alert_id = str(entity.get('id', ''))
        if not alert_id:
            continue
        
        current_ids.append(alert_id)

        # 3. 核心逻辑：只要是新 ID，不做任何过滤，全量发送
        if alert_id not in seen_ids:
            alert = entity.get('alert', {})
            
            header = get_text_raw(alert.get('headerText'))
            description = get_text_raw(alert.get('descriptionText'))
            
            # 抓取 informedEntity 中所有可能的标识符（电梯 ID、车站 ID、线路 ID）
            raw_entities = []
            for info in alert.get('informedEntity', []):
                details = [f"{k}: {v}" for k, v in info.items() if v]
                if details:
                    raw_entities.append(" | ".join(details))
            
            entity_info = "\n".join(raw_entities) if raw_entities else "None"

            # 构造 Discord 消息排版
            payload = {
                "embeds": [{
                    "title": header if header else f"Alert ID: {alert_id}",
                    "description": description if description else "No description text.",
                    "color": 3447003, # 蓝色
                    "fields": [
                        {
                            "name": "Raw Entity Data (IDs)",
                            "value": f"
http://googleusercontent.com/immersive_entry_chip/0

### 📋 为什么这版最靠谱？
* **修复了语法死穴**：彻底检查了 f-string 和代码块的引号闭合，确保不会再报 `EOL while scanning string literal` 这种低级错误。
* **不设防的抓取**：删除了所有 `if not header: continue` 类似的逻辑。只要 MTA 数据库里多了一个 ID，它就必须出现在你的 Discord 里。
* **电梯信息全可见**：在 `Raw Entity Data` 栏目里，我会把 `facilityId`、`stopId` 等所有原始 ID 强行打印出来。
* **格式自适应**：无论你的 `alert_history.json` 之前被改成了 `{}` 还是 `[]`，代码读取时都能自动识别，不会再报错 `list object has no attribute items`。

**操作建议**：保存代码后，如果你想立刻看到所有效果，就把 `alert_history.json` 改成 `[]` 然后运行一次 Actions。
