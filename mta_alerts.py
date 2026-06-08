import os
import json
import requests
import re

# Environment Variable: Discord Webhook URL
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
# State file path
STATE_FILE = "active_alerts.json"
# MTA All Services Alerts JSON API
MTA_API_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)

def send_discord_msg(title, description, color, affected_services):
    embed = {
        "title": title,
        "description": description,
        "color": color,
        "fields": [{"name": "Affected Services / Routes", "value": affected_services}],
        "footer": {"text": "MTA System-Wide Alerts"}
    }
    data = {"embeds": [embed]}
    requests.post(WEBHOOK_URL, json=data)

def fetch_mta_alerts():
    try:
        response = requests.get(MTA_API_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error fetching MTA data: {e}")
        return {}

    current_alerts = {}
    
    for entity in data.get("entity", []):
        if "alert" in entity:
            alert_id = entity["id"]
            alert_data = entity["alert"]
            
            # 1. 尝试提取 Header (兼容驼峰与下划线)
            header_obj = alert_data.get("headerText") or alert_data.get("header_text") or {}
            translations = header_obj.get("translation", [])
            header = "Unknown Alert"
            
            if translations:
                header = translations[0].get("text", "Unknown Alert")
            
            # 2. 如果 Header 为空，尝试用 Description 兜底
            if header == "Unknown Alert":
                desc_obj = alert_data.get("descriptionText") or alert_data.get("description_text") or {}
                desc_translations = desc_obj.get("translation", [])
                if desc_translations:
                    raw_text = desc_translations[0].get("text", "Unknown Alert")
                    # MTA 描述里可能有 HTML 标签，清理一下并截断防止过长
                    clean_text = re.sub(r'<[^>]+>', '', raw_text)
                    header = clean_text[:200] + "..." if len(clean_text) > 200 else clean_text

            # 3. 提取受影响实体 (兼容各类 ID)
            informed_entities = alert_data.get("informedEntity") or alert_data.get("informed_entity") or []
            affected_list = []
            
            for ie in informed_entities:
                if "routeId" in ie: affected_list.append(ie["routeId"])
                elif "route_id" in ie: affected_list.append(ie["route_id"])
                elif "agencyId" in ie: affected_list.append(ie["agencyId"])
                elif "agency_id" in ie: affected_list.append(ie["agency_id"])
                elif "stopId" in ie: affected_list.append(f"Stop {ie['stopId']}")
                elif "stop_id" in ie: affected_list.append(f"Stop {ie['stop_id']}")
                elif "facilityId" in ie: affected_list.append(f"Facility {ie['facilityId']}")
                elif "facility_id" in ie: affected_list.append(f"Facility {ie['facility_id']}")

            services = ", ".join(list(set(affected_list)))
            if not services:
                services = "System-wide / Other"

            current_alerts[alert_id] = {
                "header": header,
                "services": services
            }
            
    return current_alerts

def main():
    if not WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL is not set.")
        return

    old_alerts = load_state()
    current_alerts = fetch_mta_alerts()

    # 防刷屏核心：如果本地状态是空的，说明是首次运行。只做基准数据保存，不发送 Discord 消息。
    if not old_alerts:
        print("Initial run detected. Seeding active_alerts.json without sending webhooks to prevent spam.")
        save_state(current_alerts)
        return

    # Check for NEW alerts
    for alert_id, alert_info in current_alerts.items():
        if alert_id not in old_alerts:
            print(f"New Alert detected: {alert_info['header']}")
            send_discord_msg(
                title="⚠️ [NEW ALERT] MTA Service Alert",
                description=alert_info["header"],
                color=16711680,
                affected_services=alert_info["services"]
            )

    # Check for RESOLVED alerts
    for alert_id, alert_info in old_alerts.items():
        if alert_id not in current_alerts:
            print(f"Service Restored: {alert_info['header']}")
            send_discord_msg(
                title="✅ [RESOLVED] Service Restored",
                description=f"Cleared: {alert_info['header']}",
                color=65280,
                affected_services=alert_info["services"]
            )

    # Update the state file
    save_state(current_alerts)

if __name__ == "__main__":
    main()
