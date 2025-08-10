from flask import Flask, request
import os
import requests

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySuperSecretToken")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
HF_API_KEY = os.environ.get("HF_API_KEY")

def get_ai_reply(user_message):
    API_URL = "https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": user_message}

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        data = response.json()
        print(f"🤖 AI Response Raw: {data}")

        if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
            return data[0]["generated_text"]
        else:
            return "Sorry, I couldn't think of a reply."
    except Exception as e:
        print(f"AI API error: {e}")
        return "Sorry, something went wrong."

@app.route("/", methods=["GET"])
def home():
    return "Facebook Chatbot with AI is running!", 200

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return str(challenge), 200
        else:
            return "Verification token mismatch", 403

    elif request.method == "POST":
        data = request.get_json()
        print(f"📩 Incoming data: {data}")

        if data.get("object") == "page":
            for entry in data.get("entry", []):
                for event in entry.get("messaging", []):
                    if "message" in event:
                        sender_id = event["sender"]["id"]
                        user_message = event["message"].get("text", "")

                        if user_message:
                            ai_reply = get_ai_reply(user_message)
                            send_message(sender_id, ai_reply)
                        else:
                            send_message(sender_id, "Thanks for sending me something!")
        return "EVENT_RECEIVED", 200

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
