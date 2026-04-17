import os
from flask import Flask, jsonify
from dotenv import load_dotenv

load_dotenv()

# Import the main function from cheero_bot
from cheero_bot import main

app = Flask(__name__)


@app.route("/run-report", methods=["GET"])
def run_report():
    """Trigger the Meta ads report and send to Telegram"""
    try:
        main()
        return jsonify({"status": "success", "message": "Report sent to Telegram"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
