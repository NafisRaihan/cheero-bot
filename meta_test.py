import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("META_ACCESS_TOKEN")
ad_account_id = os.getenv("META_AD_ACCOUNT_ID")

if not token or not ad_account_id:
    raise ValueError("Missing META_ACCESS_TOKEN or META_AD_ACCOUNT_ID in .env")

url = f"https://graph.facebook.com/v19.0/{ad_account_id}/insights"

params = {
    "access_token": token,
    "level": "campaign",
    "date_preset": "last_7d",
    "fields": "campaign_name,spend,impressions,clicks,ctr,cpc,cpm",
}

response = requests.get(url, params=params, timeout=30)
print(response.status_code)
print(response.text)
