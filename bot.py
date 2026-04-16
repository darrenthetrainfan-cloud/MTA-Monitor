for entity in entities:
    alert_id = str(entity.get('id', ''))
    if not alert_id:
        continue

    new_history.append(alert_id)

    if alert_id not in seen_ids:
        alert = entity.get('alert', {})
        header = get_text(alert.get('headerText'))
        desc = get_text(alert.get('descriptionText'))

        impact_list = []

        for info in alert.get('informedEntity', []):
            details = []

            for k, v in info.items():
                if v:
                    details.append(str(k) + ": " + str(v))

            if details:
                impact_list.append(" | ".join(details))

        impact_msg = "\n".join(impact_list) if impact_list else "General Alert"

        payload = {
            "embeds": [{
                "title": "[" + mode + "] " + (header if header else "Service Update"),
                "description": (desc if desc else "No details provided.")[:4000],
                "color": 15844367,
                "fields": [
                    {
                        "name": "Affected Entities (IDs)",
                        "value": impact_msg[:1024]
                    }
                ]
            }]
        }

        requests.post(WEBHOOK_URL, json=payload, timeout=30)

with open(HISTORY_FILE, "w") as f:
    json.dump(list(set(new_history)), f)
