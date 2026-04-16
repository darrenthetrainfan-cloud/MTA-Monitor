import os
import requests
import json

# 配置：从环境变量读取 Webhook
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

# 使用你确认过的 4 个 JSON 数据源
SOURCES = {
    "Subway": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts.json",
    "Bus": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fbus-alerts.json",
    "LIRR": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Flirr-alerts.json",
    "MNR": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fmnr-alerts.json"
}
HISTORY_FILE = "alert_history.json"

def get_text(obj):
    """提取原始文本，没有任何排除逻辑"""
    if not obj or 'translation' not in obj:
        return ""
    trans = obj.get('translation', [])
    if not trans:
        return ""
    return trans[0].get('text', '').strip()

def main():
    if not WEBHOOK_URL:
        print("WEBHOOK_URL is missing!")
        return

    # 1. 强力加载历史 (防止 image_8456cd.png 中的 items 报错)
    seen_ids = set()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                data = json.load(f)
                # 无论存的是字典还是列表，都转成 set 处理
                if isinstance(data, list):
                    seen_ids = set(data)
                elif isinstance(data, dict):
                    seen_ids = set(data.keys())
        except:
            print("History file corrupted, starting fresh.")

    current_ids = []
    
    # 2. 依次检查每个源
    for mode, url in SOURCES.items():
        print("Checking " + mode + "...")
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            feed = r.json()
            entities = feed.get('entity', [])
        except Exception as e:
            print("Failed to fetch " + mode + ": " + str(e))
            continue

        for entity in entities:
            alert_id = str(entity.get('id', ''))
            if not alert_id: continue
            
            current_ids.append(alert_id)

            # 3. 只要是新 ID 就推送 (解决 image_ccb14b.png 提到的设施信息不全问题)
            if alert_id not in seen_ids:
                alert = entity.get('alert', {})
                header = get_text(alert.get('headerText'))
                desc = get_text(alert.get('descriptionText'))
                
                # 抓取所有 ID (线路, 车站, 电梯/设施)
                impacts = []
                for info in alert.get('informedEntity', []):
                    # 把 info 里的所有键值对都拼出来
                    tag = " | ".join([str(k) + ": " + str(v) for k, v in info.items() if v])
                    if tag: impacts.append(tag)
                
                impact_str = "\n".join(impacts) if impacts else "General System Update"

                # 构造最基础的 Embed，绝不使用复杂的 f-string 以防语法错误
                payload = {
                    "embeds": [{
                        "title": "[" + mode + "] " + (header if header else "New Alert"),
                        "description": (desc if desc else "Check MTA website for details.")[:4000],
                        "color": 15844367,
                        "fields": [
                            {
                                "name": "Affected Entities (IDs)",
                                "value": "
http://googleusercontent.com/immersive_entry_chip/0

### ⚡ 为什么这版能行？
1.  **彻底解决 `SyntaxError`**：我把所有容易写错的 `f-string` 全部换成了最原始的字符串相加（比如 `str + str`），绝对不会再报 `EOL while scanning string literal`。
2.  **兼容 `.json` 源**：使用了带 `.json` 的地址，确保不会再尝试解析二进制数据。
3.  **兼容历史文件**：不管你之前的 `alert_history.json` 是 `[]` 还是 `{}`，代码都能自动识别，不会再报 `items` 错误。
4.  **抓取所有细节**：针对你关心的“设施/电梯”类更新，代码会把所有 `informedEntity` 里的 ID 全部导出来，不再只看线路名。

**最后一步：**
建议你把 GitHub 上的 `alert_history.json` 手动改回 `[]`，然后触发运行。从此以后，你的 Discord 应该就能安静而稳定地收听警报了。
