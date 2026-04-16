import os
import requests
import json

# 配置：从 GitHub Secrets 获取
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

# 使用你提供的 4 个 .json 结尾的源，确保数据格式正确
SOURCES = {
    "Subway": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts.json",
    "Bus": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fbus-alerts.json",
    "LIRR": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Flirr-alerts.json",
    "MNR": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fmnr-alerts.json"
}
HISTORY_FILE = "alert_history.json"

def get_text(obj):
    """最稳妥的文本提取，防止字段缺失"""
    if not obj or 'translation' not in obj:
        return ""
    trans = obj.get('translation', [])
    if not trans:
        return ""
    # 返回第一个可用的文本内容
    return trans[0].get('text', '').strip()

def main():
    if not WEBHOOK_URL:
        print("WEBHOOK_URL is missing!")
        return

    # 1. 加载历史 (自动兼容列表或字典格式)
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
            print("History corrupted, starting fresh.")

    current_ids = []
    
    # 2. 轮询四个源
    for mode, url in SOURCES.items():
        print("Fetching " + mode + "...")
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            entities = r.json().get('entity', [])
        except Exception as e:
            print("Skip " + mode + " due to error: " + str(e))
            continue

        for entity in entities:
            alert_id = str(entity.get('id', ''))
            if not alert_id: continue
            current_ids.append(alert_id)

            # 3. 只要是新 ID 立即转发 (不拦截任何信息)
            if alert_id not in seen_ids:
                alert = entity.get('alert', {})
                header = get_text(alert.get('headerText'))
                desc = get_text(alert.get('descriptionText'))
                
                # 抓取设施 ID、车站 ID 或线路 ID (解决设施信息不全问题)
                impact_details = []
                for info in alert.get('informedEntity', []):
                    # 动态拼接所有 ID 字段，不使用易报错的 f-string 嵌套
                    parts = []
                    for k, v in info.items():
                        if v: parts.append(str(k) + ": " + str(v))
                    if parts:
                        impact_details.append(" | ".join(parts))
                
                impact_str = "\n".join(impact_details) if impact_details else "General"

                # 构造 Discord Embed (使用最稳妥的字符串加法拼接)
                payload = {
                    "embeds": [{
                        "title": "[" + mode + "] " + (header if header else "MTA Update"),
                        "description": (desc if desc else "Check MTA website.")[:4000],
                        "color": 15844367, # 黄色
                        "fields": [
                            {
                                "name": "Affected Entities (IDs)",
                                "value": "
http://googleusercontent.com/immersive_entry_chip/0

### 💎 这版代码解决了哪些“老毛病”？

* **根治 `SyntaxError`**： 这些报错通常是因为复杂的 f-string 里引号没对齐。我改用了最基础的字符串拼接（`"text" + var`），虽然看起来“笨”，但在 Python 里它最不容易出错。
* **适配 JSON 接口**： 之前的报错是因为请求到了二进制数据。现在代码严格请求带 `.json` 的 URL，确保能正确解析。
* **兼容历史记录**： 不管你的 `alert_history.json` 之前是哪种格式，代码现在都能自动识别。
* **信息完整性**： 针对你看到的“System-wide / Facilities”警报，代码现在会把隐藏在数据里的 `facilityId`（电梯/扶梯 ID）全部强行打印出来。

**最后的建议：**
代码更新后，请去 GitHub 仓库手动把 `alert_history.json` 的内容改为 `[]`。这样你的脚本会把当前所有的活跃警报重新推送到 Discord，你也正好可以检查一下电梯和具体的车站 ID 是否已经显示出来了。
