import os
import requests
from dotenv import load_dotenv

def get_runtime_config():
    if os.path.exists(".env"):
        load_dotenv()

    meta_access_token = os.environ.get("META_ACCESS_TOKEN")
    meta_ad_account_id = os.environ.get("META_AD_ACCOUNT_ID")
    telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    print("BOT TOKEN:", os.environ.get("TELEGRAM_BOT_TOKEN"))

    if not telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing")
    if not telegram_chat_id:
        raise ValueError("TELEGRAM_CHAT_ID is missing")
    if not meta_access_token:
        raise ValueError("META_ACCESS_TOKEN is missing")
    if not meta_ad_account_id:
        raise ValueError("META_AD_ACCOUNT_ID is missing")

    return {
        "meta_access_token": meta_access_token,
        "meta_ad_account_id": meta_ad_account_id,
        "telegram_bot_token": telegram_bot_token,
        "telegram_chat_id": telegram_chat_id,
    }


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


def fetch_meta_data(meta_access_token, meta_ad_account_id):
    url = f"https://graph.facebook.com/v19.0/{meta_ad_account_id}/insights"

    params = {
        "access_token": meta_access_token,
        "level": "campaign",
        "date_preset": "last_7d",
        "fields": "campaign_name,spend,impressions,clicks,ctr,cpc,actions,cost_per_action_type"
    }

    res = requests.get(url, params=params)
    return res.json().get("data", [])


def send_telegram(msg, telegram_bot_token, telegram_chat_id):
    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"

    payload = {
        "chat_id": telegram_chat_id,
        "text": msg
    }

    chat_id = telegram_chat_id
    print("Sending to chat_id:", chat_id)

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=20
        )
        print("TELEGRAM RESPONSE:", response.status_code)
        print("TELEGRAM BODY:", response.text)
        response.raise_for_status()
        return response
    except Exception as e:
        print("TELEGRAM ERROR:", str(e))
        raise


def main():
    config = get_runtime_config()

    data = fetch_meta_data(config["meta_access_token"], config["meta_ad_account_id"])

    if not data:
        return send_telegram(
            "No ads data found 😢",
            config["telegram_bot_token"],
            config["telegram_chat_id"],
        )

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

    return send_telegram(
        message,
        config["telegram_bot_token"],
        config["telegram_chat_id"],
    )


if __name__ == "__main__":
    main()
