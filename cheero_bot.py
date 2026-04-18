import json
import os
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv


API_VERSION = "v19.0"
INSIGHTS_FIELDS = "campaign_name,adset_name,spend,impressions,clicks,ctr,cpc,actions,cost_per_action_type"

INSTALL_ACTION_TYPES = ["mobile_app_install", "app_install", "omni_app_install"]
MESSAGE_ACTION_TYPES = [
    "onsite_conversion.messaging_conversation_started_7d",
    "onsite_conversion.messaging_first_reply",
    "onsite_conversion.messaging_conversation_started_14d",
]
FOLLOW_ACTION_TYPES = ["page_follow", "page_like", "like"]
SALES_ACTION_TYPES = ["purchase", "offsite_conversion.purchase", "omni_purchase"]
ALL_RESULT_ACTION_TYPES = INSTALL_ACTION_TYPES + MESSAGE_ACTION_TYPES + FOLLOW_ACTION_TYPES + SALES_ACTION_TYPES

BD_TZ = timezone(timedelta(hours=6))


def get_runtime_config():
    if os.path.exists(".env"):
        load_dotenv()

    meta_access_token = os.environ.get("META_ACCESS_TOKEN")
    meta_ad_account_id = os.environ.get("META_AD_ACCOUNT_ID")
    telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

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


def to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def format_money(value):
    return f"{to_float(value):.2f}"


def format_num(value):
    number = to_float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}"


def get_metric_value(metric_list, action_types):
    for action_type in action_types:
        for item in metric_list or []:
            if item.get("action_type") == action_type:
                return to_float(item.get("value"))
    return 0.0


def detect_objective(name):
    text = (name or "").lower()

    if any(keyword in text for keyword in ["install", "app"]):
        return "install"
    if any(keyword in text for keyword in ["msg", "message", "messenger", "whatsapp", "inbox"]):
        return "message"
    if any(keyword in text for keyword in ["sale", "sales", "purchase", "conversion"]):
        return "sales"
    if any(keyword in text for keyword in ["follow", "follower", "like", "page"]):
        return "follow"

    return "other"


def get_cost_label(objective):
    if objective == "install":
        return "Cost/Install"
    if objective == "message":
        return "Cost/Message"
    if objective == "sales":
        return "Cost/Sale"
    if objective == "follow":
        return "Cost/Follow"
    return "Cost/Result"


def fetch_insights(meta_access_token, meta_ad_account_id, level, fields, date_preset=None, time_range=None, breakdowns=None):
    url = f"https://graph.facebook.com/{API_VERSION}/{meta_ad_account_id}/insights"
    params = {
        "access_token": meta_access_token,
        "level": level,
        "fields": fields,
        "limit": 200,
    }

    if date_preset:
        params["date_preset"] = date_preset
    if time_range:
        params["time_range"] = json.dumps(time_range)
    if breakdowns:
        params["breakdowns"] = ",".join(breakdowns)

    all_rows = []
    next_url = url
    next_params = params

    while next_url:
        response = requests.get(next_url, params=next_params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        all_rows.extend(payload.get("data", []))
        next_url = payload.get("paging", {}).get("next")
        next_params = None

    return all_rows


def fetch_insights_safe(meta_access_token, meta_ad_account_id, level, fields, date_preset=None, time_range=None, breakdowns=None):
    try:
        return fetch_insights(
            meta_access_token,
            meta_ad_account_id,
            level=level,
            fields=fields,
            date_preset=date_preset,
            time_range=time_range,
            breakdowns=breakdowns,
        )
    except Exception:
        return []


def normalize_adset_row(row):
    actions = row.get("actions", [])
    cost_per_action_type = row.get("cost_per_action_type", [])

    install_count = get_metric_value(actions, INSTALL_ACTION_TYPES)
    message_count = get_metric_value(actions, MESSAGE_ACTION_TYPES)
    follow_count = get_metric_value(actions, FOLLOW_ACTION_TYPES)
    sales_count = get_metric_value(actions, SALES_ACTION_TYPES)

    objective_name = f"{row.get('campaign_name', '')} {row.get('adset_name', '')}".strip()
    objective = detect_objective(objective_name)

    if objective == "other":
        action_signal = {
            "install": install_count,
            "message": message_count,
            "sales": sales_count,
            "follow": follow_count,
        }
        inferred_objective, inferred_value = max(action_signal.items(), key=lambda item: item[1])
        if inferred_value > 0:
            objective = inferred_objective

    if objective == "install":
        result_label = "Installs"
        result_count = install_count
        cost_per_result = get_metric_value(cost_per_action_type, INSTALL_ACTION_TYPES)
    elif objective == "message":
        result_label = "Messages"
        result_count = message_count
        cost_per_result = get_metric_value(cost_per_action_type, MESSAGE_ACTION_TYPES)
    elif objective == "sales":
        result_label = "Purchases"
        result_count = sales_count
        cost_per_result = get_metric_value(cost_per_action_type, SALES_ACTION_TYPES)
    elif objective == "follow":
        result_label = "Follows"
        result_count = follow_count
        cost_per_result = get_metric_value(cost_per_action_type, FOLLOW_ACTION_TYPES)
    else:
        result_label = "Results"
        result_count = get_metric_value(actions, ALL_RESULT_ACTION_TYPES)
        cost_per_result = 0.0

    spend = to_float(row.get("spend"))
    ctr = to_float(row.get("ctr"))
    cpc = to_float(row.get("cpc"))

    if spend > 0 and result_count > 0:
        score = (result_count / spend) * 100
    else:
        score = ctr - cpc

    return {
        "campaign_name": row.get("campaign_name") or "Unknown Campaign",
        "adset_name": row.get("adset_name") or "Unknown Ad Set",
        "objective": objective,
        "cost_label": get_cost_label(objective),
        "spend": spend,
        "impressions": to_int(row.get("impressions")),
        "clicks": to_int(row.get("clicks")),
        "ctr": ctr,
        "cpc": cpc,
        "result_label": result_label,
        "result_count": result_count,
        "cost_per_result": cost_per_result,
        "score": score,
    }


def select_top_rows(rows, limit=3):
    filtered = [row for row in rows if row["spend"] > 0]
    return sorted(filtered, key=lambda item: item["score"], reverse=True)[:limit]


def select_worst_rows(rows, limit=3):
    filtered = [row for row in rows if row["spend"] > 0]
    return sorted(filtered, key=lambda item: item["score"])[:limit]


def get_day_label(days_ago):
    return (datetime.now(BD_TZ).date() - timedelta(days=days_ago)).isoformat()


def build_day_compare_map(rows):
    mapping = {}
    for row in rows:
        key = row.get("adset_name") or "Unknown Ad Set"
        mapping[key] = normalize_adset_row(row)
    return mapping


def best_row_from_breakdown(rows):
    best = None
    best_score = float("-inf")
    for row in rows:
        spend = to_float(row.get("spend"))
        ctr = to_float(row.get("ctr"))
        cpc = to_float(row.get("cpc"), default=9999)
        results = get_metric_value(row.get("actions", []), ALL_RESULT_ACTION_TYPES)
        if spend > 0 and results > 0:
            score = (results / spend) * 100
        else:
            score = ctr - cpc

        if score > best_score:
            best_score = score
            best = row
    return best


def build_recommendations(best_rows, worst_rows, increasing_cost_rows):
    recommendations = []

    if best_rows:
        best = best_rows[0]
        recommendations.append(
            f"Scale {best['adset_name']} (+15-20% budget) because it's currently the most efficient."
        )

    high_spend_low_result = [
        row for row in worst_rows if row["spend"] >= 300 and row["result_count"] == 0
    ]
    if high_spend_low_result:
        recommendations.append(
            f"Review or pause {high_spend_low_result[0]['adset_name']} (high spend with no measurable result)."
        )

    if increasing_cost_rows:
        recommendations.append(
            "Audit creatives/audience in cost-increasing ad sets and duplicate top winner ad copy in a new test ad set."
        )

    if not recommendations:
        recommendations.append("Performance is stable; continue current setup and monitor daily.")

    return recommendations[:3]


def build_segment_summary(rows):
    segments = {
        "install": {"name": "Install Ads", "result_label": "Installs", "cost_label": "Cost/Install", "spend": 0.0, "results": 0.0},
        "message": {"name": "Message Ads", "result_label": "Messages", "cost_label": "Cost/Message", "spend": 0.0, "results": 0.0},
        "sales": {"name": "Sales Ads", "result_label": "Sales", "cost_label": "Cost/Sale", "spend": 0.0, "results": 0.0},
        "follow": {"name": "Follow Ads", "result_label": "Follows", "cost_label": "Cost/Follow", "spend": 0.0, "results": 0.0},
        "other": {"name": "Other Ads", "result_label": "Results", "cost_label": "Cost/Result", "spend": 0.0, "results": 0.0},
    }

    for row in rows:
        objective = row.get("objective", "other")
        if objective not in segments:
            objective = "other"

        segments[objective]["spend"] += row.get("spend", 0.0)
        segments[objective]["results"] += row.get("result_count", 0.0)

    ordered_keys = ["install", "message", "sales", "follow", "other"]
    return [segments[key] for key in ordered_keys if segments[key]["spend"] > 0]


def split_message(text, max_chars=3500):
    lines = text.split("\n")
    chunks = []
    current = ""

    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > max_chars:
            if current:
                chunks.append(current)
            current = line
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks


def send_telegram(msg, telegram_bot_token, telegram_chat_id):
    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    responses = []

    for chunk in split_message(msg):
        payload = {
            "chat_id": telegram_chat_id,
            "text": chunk,
        }
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        responses.append(response)

    return responses[-1]


def build_report_message(today_rows, age_gender_rows, country_rows, time_rows, placement_rows):
    normalized = [normalize_adset_row(row) for row in today_rows]
    normalized = [row for row in normalized if row["spend"] > 0]

    if not normalized:
        return "No ads data found for the selected period 😢"

    total_spend_today = sum(row["spend"] for row in normalized)
    segment_summary = build_segment_summary(normalized)
    best_rows = select_top_rows(normalized, limit=3)
    worst_rows = select_worst_rows(normalized, limit=3)
    adset_snapshot = sorted(normalized, key=lambda item: item["spend"], reverse=True)[:8]

    best_age_gender = best_row_from_breakdown(age_gender_rows)
    best_country = best_row_from_breakdown(country_rows)
    best_time = best_row_from_breakdown(time_rows)
    best_placement = best_row_from_breakdown(placement_rows)

    recommendations = build_recommendations(best_rows, worst_rows, [])

    report_date = get_day_label(0)

    lines = []
    lines.append("📊 CHEERO Meta Ads Today Report")
    lines.append(f"🗓 Date (BD): {report_date} | Report Time: 9:00 PM (BD)")
    lines.append("")

    lines.append("🧾 Summary")
    lines.append(f"- Total Budget Spent Today: {format_money(total_spend_today)}")
    lines.append("")

    lines.append("📌 Segment-wise Budget & Results")
    for segment in segment_summary:
        results = segment["results"]
        spend = segment["spend"]
        cpr = spend / results if results > 0 else 0.0
        cost_value = format_money(cpr) if results > 0 else "N/A"
        lines.append(
            f"- {segment['name']}: Spend {format_money(spend)} | {segment['result_label']} {format_num(results)} | {segment['cost_label']} {cost_value}"
        )
    lines.append("")

    lines.append("🔥 Best Performing Ad Sets")
    for index, row in enumerate(best_rows, start=1):
        lines.append(
            f"{index}. {row['adset_name']} ({row['objective'].title()})"
        )
        lines.append(
            f"   • {row['result_label']}: {format_num(row['result_count'])} | {row['cost_label']}: {format_money(row['cost_per_result'])} | Spend: {format_money(row['spend'])}"
        )
    lines.append("")

    lines.append("⚠️ Worst Performing Ad Sets")
    for index, row in enumerate(worst_rows, start=1):
        lines.append(
            f"{index}. {row['adset_name']} ({row['objective'].title()})"
        )
        lines.append(
            f"   • {row['result_label']}: {format_num(row['result_count'])} | {row['cost_label']}: {format_money(row['cost_per_result'])} | Spend: {format_money(row['spend'])}"
        )
    lines.append("")

    lines.append("📦 Ad Set-wise Snapshot (Top by Spend)")
    for index, row in enumerate(adset_snapshot, start=1):
        lines.append(
            f"{index}. {row['adset_name']} ({row['objective'].title()})"
        )
        lines.append(
            f"   • CTR: {row['ctr']:.2f}% | CPC: {format_money(row['cpc'])} | {row['result_label']}: {format_num(row['result_count'])}"
        )
        lines.append(
            f"   • {row['cost_label']}: {format_money(row['cost_per_result'])} | Spend: {format_money(row['spend'])}"
        )
    lines.append("")

    lines.append("🧠 Best Performing Demography")
    has_demography_line = False
    if best_age_gender:
        lines.append(f"- Age/Gender: {best_age_gender.get('age', 'N/A')} | {best_age_gender.get('gender', 'N/A')}")
        has_demography_line = True
    if best_country:
        lines.append(f"- Location: {best_country.get('country', 'N/A')}")
        has_demography_line = True
    if best_time:
        lines.append(
            f"- Time: {best_time.get('hourly_stats_aggregated_by_advertiser_time_zone', 'N/A')}"
        )
        has_demography_line = True
    if best_placement:
        lines.append(
            f"- Placement: {best_placement.get('publisher_platform', 'N/A')} / {best_placement.get('platform_position', 'N/A')}"
        )
        has_demography_line = True
    if not has_demography_line:
        lines.append("- Breakdown data unavailable for this ad account.")
    lines.append("")

    lines.append("✅ Recommendations")
    for recommendation in recommendations:
        lines.append(f"- {recommendation}")

    return "\n".join(lines)


def main():
    config = get_runtime_config()

    today_date = get_day_label(0)

    today_rows = fetch_insights(
        config["meta_access_token"],
        config["meta_ad_account_id"],
        level="adset",
        fields=INSIGHTS_FIELDS,
        time_range={"since": today_date, "until": today_date},
    )

    age_gender_rows = fetch_insights_safe(
        config["meta_access_token"],
        config["meta_ad_account_id"],
        level="adset",
        fields="spend,ctr,cpc,actions,age,gender",
        time_range={"since": today_date, "until": today_date},
        breakdowns=["age", "gender"],
    )

    country_rows = fetch_insights_safe(
        config["meta_access_token"],
        config["meta_ad_account_id"],
        level="adset",
        fields="spend,ctr,cpc,actions,country",
        time_range={"since": today_date, "until": today_date},
        breakdowns=["country"],
    )

    time_rows = fetch_insights_safe(
        config["meta_access_token"],
        config["meta_ad_account_id"],
        level="adset",
        fields="spend,ctr,cpc,actions,hourly_stats_aggregated_by_advertiser_time_zone",
        time_range={"since": today_date, "until": today_date},
        breakdowns=["hourly_stats_aggregated_by_advertiser_time_zone"],
    )

    placement_rows = fetch_insights_safe(
        config["meta_access_token"],
        config["meta_ad_account_id"],
        level="adset",
        fields="spend,ctr,cpc,actions,publisher_platform,platform_position",
        time_range={"since": today_date, "until": today_date},
        breakdowns=["publisher_platform", "platform_position"],
    )

    message = build_report_message(
        today_rows,
        age_gender_rows,
        country_rows,
        time_rows,
        placement_rows,
    )

    return send_telegram(
        message,
        config["telegram_bot_token"],
        config["telegram_chat_id"],
    )


if __name__ == "__main__":
    main()
