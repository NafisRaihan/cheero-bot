import os
from flask import Flask, jsonify

# Import the main function from cheero_bot
from cheero_bot import main

app = Flask(__name__)


def send_report_to_telegram():
    return main()


@app.route("/run-report", methods=["GET"])
def run_report():
    # call your existing report function here
    try:
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        chat_id = os.environ["TELEGRAM_CHAT_ID"]
        meta_token = os.environ["META_ACCESS_TOKEN"]
        ad_account_id = os.environ["META_AD_ACCOUNT_ID"]

        print("BOT TOKEN EXISTS:", bool(token))
        print("CHAT ID:", chat_id)

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
    import os
    return {
        "TELEGRAM_BOT_TOKEN": bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
        "TELEGRAM_CHAT_ID": bool(os.environ.get("TELEGRAM_CHAT_ID")),
        "META_ACCESS_TOKEN": bool(os.environ.get("META_ACCESS_TOKEN")),
        "META_AD_ACCOUNT_ID": bool(os.environ.get("META_AD_ACCOUNT_ID")),
        "TEST_MARKER": os.environ.get("TEST_MARKER"),
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
