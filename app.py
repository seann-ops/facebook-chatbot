import os
import sys
import requests
from flask import Flask, request

app = Flask(__name__)

# =====================
# CONFIG
# =====================
VERIFY_TOKEN = "MySuperSecretToken"  # Must match the one in Facebook webhook settings
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "your_page_access_token_here")

# =====================
# ROOT ROUTE
# =====================
@app.route("/", methods=["GET"])
def home():
    return "Facebook Chatbot is running!", 200

# =====================
# WEBHOOK VERIFICATION
# =====================
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    # Facebook sends a GET request to verify webhook
    verify_token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if verify_token == VERIFY_TOKEN:
        return challenge, 200
    else:
        return "Verification token mismatch", 403

# =====================
# MESSAGE HANDLING
# =====================
@app.route("/webhook", methods=["POST"])
def handle_messages():
    data = request.get_json()

    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]

                if "message" in messaging_event:
                    message_text = messaging_event["message"].get("text", "")
                    send_message(sender_id, f"You said: {message_text}")

    return "ok", 200

# =====================
# SEND MESSAGE FUNCTION
# =====================
def send_message(recipient_id, message_text):
    params = {
        "access_token": PAGE_ACCESS_TOKEN
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }

    r = requests.post(
        "https://graph.facebook.com/v18.0/me/messages",
        params=params,
        headers=headers,
        json=data
    )

    if r.status_code != 200:
        print(f"Error sending message: {r.status_code} - {r.text}", file=sys.stderr)

# =====================
# MAIN ENTRY
# =====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
