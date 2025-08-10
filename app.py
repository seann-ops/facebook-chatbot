from flask import Flask, request
import os
import requests

app = Flask(__name__)

# Environment variables from Render
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySuperSecretToken")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "your_page_access_token_here")

# Root route
@app.route("/", methods=["GET"])
def home():
    return "Facebook Chatbot is running!", 200

# Facebook webhook verification & message handler
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        # Verification step
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        # Debug logs
        print("🔍 Facebook Verification Request:")
        print(f"mode = {mode}")
        print(f"token = {token}")
        print(f"challenge = {challenge}")
        print(f"Expected VERIFY_TOKEN = {VERIFY_TOKEN}")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("✅ WEBHOOK VERIFIED - Returning challenge")
            return str(challenge), 200
        else:
            print("❌ VERIFICATION FAILED - Token mismatch")
            return "Verification token mismatch", 403

    elif request.method == "POST":
        # Handle incoming messages
        data = request.get_json()
        print(f"📩 Incoming data: {data}")

        if data.get("object") == "page":
            for entry in data.get("entry", []):
                for event in entry.get("messaging", []):
                    if "message" in event:
                        sender_id = event["sender"]["id"]
                        message_text = event["message"].get("text", "")
                        send_message(sender_id, f"You said: {message_text}")
        return "EVENT_RECEIVED", 200


# Send message to user
def send_message(recipient_id, message_text):
    if not PAGE_ACCESS_TOKEN:
        print("❌ PAGE_ACCESS_TOKEN not set.")
        return

    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }

    response = requests.post(
        "https://graph.facebook.com/v18.0/me/messages",
        params=params, headers=headers, json=data
    )

    print(f"📤 Sent message to {recipient_id}: {message_text}")
    print(f"Facebook API response: {response.status_code} - {response.text}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
