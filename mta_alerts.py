import os
import json
import time
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from google.transit import gtfs_realtime_pb2

# --- 配置日志 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class MTAAlertBot:
    def __init__(self):
        self.feed_url = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts"
        self.webhook_url = os.environ.get("DISCORD_WEBHOOK")
        self.state_file = "seen_alerts.json"
        self.max_alerts_per_run = 15  # 防刷屏阈值
        
        # 建立带重试机制的 HTTP Session
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def load_state(self) -> set:
        """加载已见过的 Alert ID"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    return set(json.loads(content)) if content else set()
            except Exception as e:
                logging.error(f"读取状态文件失败，将重置状态: {e}")
        return set()

    def save_state(self, current_ids: set, seen_ids: set):
        """保存状态，自动清理已失效的过期 Alert ID"""
        active_seen_ids = seen_ids.intersection(current_ids)
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(list(active_seen_ids), f)
            logging.info(f"状态已保存。当前追踪中活跃警报数: {len(active_seen_ids)}")
        except Exception as e:
            logging.error(f"写入状态文件失败: {e}")

    def fetch_mta_data(self) -> gtfs_realtime_pb2.FeedMessage:
        """获取并解析 MTA GTFS 数据"""
        feed = gtfs_realtime_pb2.FeedMessage()
        try:
            response = self.session.get(self.feed_url, timeout=15)
            response.raise_for_status()
            feed.ParseFromString(response.content)
            return feed
        except Exception as e:
            logging.error(f"获取或解析 MTA 数据失败: {e}")
            return None

    def send_to_discord(self, alert, alert_id: str):
        """格式化并发送单条警报至 Discord"""
        header = alert.header_text.translation[0].text if alert.header_text.translation else "MTA Service Alert"
        desc = alert.description_text.translation[0].text if alert.description_text.translation else "No details provided."
        
        # 截断超长描述
        if len(desc) > 1000:
            desc = desc[:1000] + "...\n\n*[Text truncated]*"

        # 提取受影响线路并排序
        affected_lines = sorted({entity.route_id for entity in alert.informed_entity if entity.route_id})
        lines_str = ", ".join(affected_lines) if affected_lines else "System-wide"

        payload = {
            "embeds": [{
                "title": header[:256],
                "description": desc,
                "color": 15158332, # MTA 警报红
                "fields": [{"name": "Affected Lines", "value": f"`{lines_str}`", "inline": True}],
                "footer": {"text": f"Alert ID: {alert_id}"},
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }]
        }

        try:
            r = self.session.post(self.webhook_url, json=payload, timeout=10)
            if r.status_code not in (200, 204):
                logging.error(f"Discord 响应错误 (HTTP {r.status_code}): {r.text}")
        except Exception as e:
            logging.error(f"发送 Webhook 失败 [{alert_id}]: {e}")

    def run(self):
        if not self.webhook_url:
            logging.error("未检测到 DISCORD_WEBHOOK 环境变量，退出运行。")
            return

        logging.info("开始拉取 MTA 警报数据...")
        feed = self.fetch_mta_data()
        if not feed: return

        seen_ids = self.load_state()
        current_ids = set()
        new_alerts = []

        # 解析全部警报
        for entity in feed.entity:
            if entity.HasField('alert'):
                alert_id = str(entity.id)
                current_ids.add(alert_id)
                if alert_id not in seen_ids:
                    new_alerts.append(entity)

        logging.info(f"解析完毕。总计活跃警报: {len(current_ids)}，发现新警报: {len(new_alerts)}")

        # 防刷屏与发送逻辑
        if len(new_alerts) > self.max_alerts_per_run:
            logging.warning(f"新警报数量({len(new_alerts)})超过防刷屏阈值({self.max_alerts_per_run})。触发静默模式，仅更新数据库。")
            for entity in new_alerts:
                seen_ids.add(str(entity.id))
        else:
            for entity in new_alerts:
                alert_id = str(entity.id)
                logging.info(f"推送警报至 Discord: {alert_id}")
                self.send_to_discord(entity.alert, alert_id)
                seen_ids.add(alert_id)
                time.sleep(1.5)  # 严格保护 Discord API 速率限制

        # 更新本地状态
        self.save_state(current_ids, seen_ids)
        logging.info("本次运行任务圆满结束。")

if __name__ == "__main__":
    bot = MTAAlertBot()
    bot.run()
