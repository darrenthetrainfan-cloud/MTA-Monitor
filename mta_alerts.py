import os
import json
import requests

# Environment Variable: Discord Webhook URL
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
# State file path
STATE_FILE = "active_alerts.json"
# MTA All Services Alerts JSON API (Covers Subway, Bus, LIRR, Metro-North, Bridges & Tunnels)
MTA_API_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts.json"

def load_state():
    """Load the alert state from the previous run"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_state(state):
    """Save the current alert state to a file"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)

def send_discord_msg(title, description, color, affected_services):
    """Send an Embed message to Discord"""
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
    """Fetch and parse current MTA alerts for all services"""
    try:
        response = requests.get(MTA_API_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error fetching MTA data: {e}")
        return {}

    current_alerts = {}
    
    # Parse GTFS-Realtime JSON structure
    for entity in data.get("entity", []):
        if "alert" in entity:
            alert_id = entity["id"]
            alert_data = entity["alert"]
            
            # Extract header text
            header = alert_data.get("headerText", {}).get("translation", [{"text": "Unknown Alert"}])[0].get("text")
            
            # Extract affected routes or agencies
            informed_entities = alert_data.get("informedEntity", [])
            affected_list = []
            
            for ie in informed_entities:
                if "routeId" in ie:
                    affected_list.append(ie["routeId"])
                elif "agencyId" in ie:
                    # Fallback to agency ID (e.g., "LIRR", "MNR", "MTABC") if no specific route is given
                    affected_list.append(ie["agencyId"])
            
            # Remove duplicates and join
            services = ", ".join(list(set(affected_list)))
            if not services:
                services = "System-wide / Multiple Agencies"

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

    # 1. Check for NEW alerts
    for alert_id, alert_info in current_alerts.items():
        if alert_id not in old_alerts:
            print(f"New Alert detected: {alert_info['header']}")
            send_discord_msg(
                title="⚠️ [NEW ALERT] MTA Service Alert",
                description=alert_info["header"],
                color=16711680, # Red
                affected_services=alert_info["services"]
            )

    # 2. Check for RESOLVED alerts
    for alert_id, alert_info in old_alerts.items():
        if alert_id not in current_alerts:
            print(f"Service Restored: {alert_info['header']}")
            send_discord_msg(
                title="✅ [RESOLVED] Service Restored",
                description=f"Cleared: {alert_info['header']}",
                color=65280, # Green
                affected_services=alert_info["services"]
            )

    # 3. Update the state file
    save_state(current_alerts)

if __name__ == "__main__":
    main()
