import os
import requests
import json

# Config
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
HISTORY_FILE = "alert_history.json"

SOURCES = {
    "Subway": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts.json",
    "Bus": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fbus-alerts.json",
    "LIRR": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Flirr-alerts.json",
    "MNR": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fmnr-alerts.json",
}


def get_text(obj):
    """Safely extract translated text."""
    if not obj or "translation" not in obj:
        return ""

    trans = obj.get("translation", [])
    if not trans:
        return ""

    return trans[0].get("text", "").strip()



def load_history():
    """Load previously seen alert IDs."""
    if not os.path.exists(HISTORY_FILE):
        return set()

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return set(str(x) for x in data)
        if isinstance(data, dict):
            return set(str(k) for k in data.keys())

    except Exception as e:
        print("History load error:", e)

    return set()



def save_history(history_ids):
    """Persist alert history."""
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(history_ids)), f, indent=2)
    except Exception as e:
        print("History save error:", e)



def send_discord_alert(mode, header, desc, impact_msg):
    """Send a single alert embed to Discord."""
    payload = {
        "embeds": [
            {
                "title": "[" + mode + "] " + (header or "Service Update"),
                "description": (desc or "No details provided.")[:4000],
                "color": 15844367,
                "fields": [
                    {
                        "name": "Affected Entities (IDs)",
                        "value": impact_msg[:1024],
                    }
                ],
            }
        ]
    }

    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=30)
        response.raise_for_status()
        print("Sent alert to Discord")
    except Exception as e:
        print("Discord send error:", e)



def main():
    if not WEBHOOK_URL:
        print("Missing DISCORD_WEBHOOK_URL")
        return

    seen_ids = load_history()
    all_current_ids = set(seen_ids)

    for mode, url in SOURCES.items():
        print("Fetching " + mode + "...")

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            entities = data.get("entity", [])
        except Exception as e:
            print(mode + " fetch error:", e)
            continue

        for entity in entities:
            alert_id = str(entity.get("id", "")).strip()
            if not alert_id:
                continue

            all_current_ids.add(alert_id)

            # Only send unseen alerts
            if alert_id in seen_ids:
                continue

            alert = entity.get("alert", {})
            header = get_text(alert.get("headerText"))
            desc = get_text(alert.get("descriptionText"))

            impact_list = []
            for info in alert.get("informedEntity", []):
                details = []
                for key, value in info.items():
                    if value:
                        details.append(str(key) + ": " + str(value))

                if details:
                    impact_list.append(" | ".join(details))

            impact_msg = "\n".join(impact_list) if impact_list else "General Alert"

            print("New alert found:", alert_id)
            send_discord_alert(mode, header, desc, impact_msg)

    save_history(all_current_ids)
    print("Run complete")


if __name__ == "__main__":
    main()
