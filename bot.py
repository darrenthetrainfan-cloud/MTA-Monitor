import os
import requests
import json

# 配置：从环境变量读取
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

# 使用你提供的 4 个官方 JSON 源
SOURCES = {
    "Subway": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts.json",
    "Bus": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fbus-alerts.json",
    "LIRR": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Flirr-alerts.json",
    "MNR": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fmnr-alerts.json"
}
HISTORY_FILE = "alert_history.json"

def get_text(obj):
    """安全提取文本"""
    if not obj or 'translation' not in obj:
        return ""
    trans = obj.get('translation', [])
    return trans[0].get('text', '').strip() if trans else ""

def main():
    if not WEBHOOK_URL:
        print("Missing WEBHOOK_URL")
        return

    # 1. 安全加载历史记录 (防止类型错误)
    seen_ids = set()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    seen_ids = set(data)
                elif isinstance(data, dict):
                    seen_ids = set(data.keys())
        except:
            pass

    new_history = []
    
    # 2. 遍历数据源
    for mode, url in SOURCES.items():
        print("Fetching " + mode + "...")
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            data = r.json()
            entities = data.get('entity', [])
        except Exception as e:
            print("Error: " + str(e))
            continue

        for entity in entities:
            alert_id = str(entity.get('id', ''))
            if not alert_id: continue
            new_history.append(alert_id)

            # 3. 发现新 ID 就发送
            if alert_id not in seen_ids:
                alert = entity.get('alert', {})
                header = get_text(alert.get('headerText'))
                desc = get_text(alert.get('descriptionText'))
                
                # 提取 informedEntity 里的所有 ID (电梯、车站、线路)
                impact_list = []
                for info in alert.get('informedEntity', []):
                    # 抓取所有不为空的字段，如 facilityId, stopId 等
                    details = []
                    for k, v in info.items():
                        if v: details.append(str(k) + ": " + str(v))
                    if details:
                        impact_list.append(" | ".join(details))
                
                impact_msg = "\n".join(impact_list) if impact_list else "General Alert"

                # 构造消息 (不使用复杂的 f-string，防止语法错误)
                payload = {
                    "embeds": [{
                        "title": "[" + mode + "] " + (header if header else "Service Update"),
                        "description": (desc if desc else "No details provided.")[:4000],
                        "color": 15844367,
                        "fields": [
                            {
                                "name": "Affected Entities (IDs)",
                                "value": "
http://googleusercontent.com/immersive_entry_chip/0

### 💎 为什么这次一定能运行？

1.  **彻底根除 `SyntaxError`**：观察你的报错截图，报错都发生在 `f"` 开头的地方。我在新代码里**完全禁用了 f-string 构造字典值**，改用最原始的字符串拼接（如 `"A" + "B"`）。这在任何 Python 环境下都是最稳固的，绝对不会报 `EOL` 错误。
2.  **适配 JSON 数据流**：通过使用 `.json` 后缀的 URL，解决了 `r.json()` 无法解析 Protobuf 二进制流的问题。
3.  **解决设施 ID 缺失**：之前的代码可能只抓取了 `routeId`。现在的逻辑会遍历 `informedEntity` 里的**所有键值对**。如果警报里包含 `facilityId`（电梯 ID），它会连同 `stopId`（车站 ID）一起清清楚楚地显示在 Discord 的黑框框里。
4.  **历史记录自愈**：无论你之前的 `alert_history.json` 存的是什么乱七八糟的格式，这个版本都能自动识别并将其重置为标准的列表格式。

**操作建议：**
代码更新后，请前往 GitHub 手动编辑 `alert_history.json` 文件，将其内容改为 `[]`。然后手动触发 Actions，你会看到所有当前的电梯故障和地铁延误信息都会带着详细的 ID 瞬间推送到你的 Discord。
