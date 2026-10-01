import os
import threading
import time
from datetime import datetime, timedelta

from flask import Flask, jsonify

# Import the main function from cheero_bot
from cheero_bot import BD_TZ, main

REPORT_HOUR, REPORT_MINUTE = 23, 59

app = Flask(__name__)


def send_report_to_telegram():
    return main()


@app.route("/run-report", methods=["GET"])
def run_report():
    # call your existing report function here
    try:
        os.environ["TELEGRAM_BOT_TOKEN"]
        os.environ["TELEGRAM_CHAT_ID"]
        os.environ["META_ACCESS_TOKEN"]
        os.environ["META_AD_ACCOUNT_ID"]

        response = send_report_to_telegram()
        return response.json()
    except KeyError as e:
        return {"status": "error", "message": f"missing {e.args[0]}"}, 500
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok"}), 200


@app.route("/env-check", methods=["GET"])
def env_check():
    return {
        "TELEGRAM_BOT_TOKEN": bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
        "TELEGRAM_CHAT_ID": bool(os.environ.get("TELEGRAM_CHAT_ID")),
        "META_ACCESS_TOKEN": bool(os.environ.get("META_ACCESS_TOKEN")),
        "META_AD_ACCOUNT_ID": bool(os.environ.get("META_AD_ACCOUNT_ID")),
    }


def seconds_until_next_report(now):
    target = now.replace(hour=REPORT_HOUR, minute=REPORT_MINUTE, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def report_scheduler():
    """Send the daily report at 23:59 BD. Runs in-process because GitHub's
    cron schedule was firing up to 4 hours late."""
    while True:
        wait = seconds_until_next_report(datetime.now(BD_TZ))
        print(f"[scheduler] next report in {wait / 3600:.2f}h", flush=True)
        time.sleep(wait)
        try:
            main()
            print("[scheduler] report sent", flush=True)
        except Exception as e:
            print(f"[scheduler] report failed: {e}", flush=True)
        time.sleep(90)  # step past 23:59 so the next wait targets tomorrow


if __name__ == "__main__":
    threading.Thread(target=report_scheduler, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
