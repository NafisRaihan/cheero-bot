import os
import requests
from dotenv import load_dotenv

load_dotenv()

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
META_AD_ACCOUNT_ID = os.getenv("META_AD_ACCOUNT_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


INSTALL_ACTION_TYPES = ["mobile_app_install", "app_install", "omni_app_install"]
MESSAGE_ACTION_TYPES = [
    "onsite_conversion.messaging_conversation_started_7d",
    "onsite_conversion.messaging_first_reply",
    "onsite_conversion.messaging_conversation_started_14d",
]
FOLLOW_ACTION_TYPES = ["page_follow", "page_like", "like"]


def get_metric_value(metric_list, action_types):
    for action_type in action_types:
        for item in metric_list or []:
            if item.get("action_type") == action_type:
                return item.get("value")
    return None


def detect_campaign_type(campaign_name):
    name = (campaign_name or "").lower()

    if any(keyword in name for keyword in ["install", "app"]):
        return "install"
    if any(keyword in name for keyword in ["msg", "message", "messenger", "whatsapp", "inbox"]):
        return "message"
    if any(keyword in name for keyword in ["follow", "follower", "like", "page"]):
        return "follow"

    return "other"


def fetch_meta_data():
    url = f"https://graph.facebook.com/v19.0/{META_AD_ACCOUNT_ID}/insights"

    params = {
        "access_token": META_ACCESS_TOKEN,
        "level": "campaign",
        "date_preset": "last_7d",
        "fields": "campaign_name,spend,impressions,clicks,ctr,cpc,actions,cost_per_action_type"
    }

    res = requests.get(url, params=params)
    return res.json().get("data", [])


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg
    }

    requests.post(url, json=payload)


def main():
    data = fetch_meta_data()

    if not data:
        send_telegram("No ads data found 😢")
        return

    message = "📊 Meta Ads Report (Last 7 Days)\n\n"

    for row in data[:5]:
        campaign_type = detect_campaign_type(row.get("campaign_name"))
        actions = row.get("actions", [])
        cost_per_action_type = row.get("cost_per_action_type", [])

        install_count = get_metric_value(actions, INSTALL_ACTION_TYPES)
        cost_per_install = get_metric_value(cost_per_action_type, INSTALL_ACTION_TYPES)

        message_count = get_metric_value(actions, MESSAGE_ACTION_TYPES)
        cost_per_message = get_metric_value(cost_per_action_type, MESSAGE_ACTION_TYPES)

        follow_count = get_metric_value(actions, FOLLOW_ACTION_TYPES)
        cost_per_follow = get_metric_value(cost_per_action_type, FOLLOW_ACTION_TYPES)

        message += f"🎯 {row.get('campaign_name')}\n"
        message += f"🏷 Type: {campaign_type.title()}\n"
        message += f"💰 Spend: {row.get('spend')}\n"
        message += f"👁 Impressions: {row.get('impressions')}\n"
        message += f"🖱 Clicks: {row.get('clicks')}\n"
        message += f"📈 CTR: {row.get('ctr')}\n"
        message += f"💸 CPC: {row.get('cpc')}\n"

        if campaign_type == "install":
            message += f"📲 Installs: {install_count or 'N/A'}\n"
            message += f"💵 Cost/Install: {cost_per_install or 'N/A'}\n"
        elif campaign_type == "message":
            message += f"💬 Messages: {message_count or 'N/A'}\n"
            message += f"💵 Cost/Message: {cost_per_message or 'N/A'}\n"
        elif campaign_type == "follow":
            message += f"👍 Likes/Follows: {follow_count or 'N/A'}\n"
            message += f"💵 Cost/Like-Follow: {cost_per_follow or 'N/A'}\n"

        message += "----------------------\n"

    send_telegram(message)


if __name__ == "__main__":
    main()
