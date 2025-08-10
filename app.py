from flask import Flask, request
import os
import requests
from collections import defaultdict

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySuperSecretToken")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# Store conversation history per user: user and bot messages alternate
conversation_history = defaultdict(list)

def get_ai_reply(user_id, user_message):
    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = "You are a helpful AI assistant."

    messages = [{"role": "system", "content": system_prompt}]

    # Append previous conversation from memory
    for i, msg in enumerate(conversation_history[user_id]):
        role = "user" if i % 2 == 0 else "assistant"
        messages.append({"role": role, "content": msg})

    # Append current user message
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": "DeepSeek: DeepSeek V3 0324 (free)",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 150
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"OpenRouter API error: {response.status_code} - {response.text}")
            return "Sorry, I couldn't get a reply from AI service."

        data = response.json()
        ai_text = data["choices"][0]["message"]["content"]

        # Update conversation history
        conversation_history[user_id].append(user_message)  # user message
        conversation_history[user_id].append(ai_text)       # bot reply

        # Keep last 10 messages max (5 user-bot pairs)
        if len(conversation_history[user_id]) > 10:
            conversation_history[user_id] = conversation_history[user_id][-10:]

        return ai_text

    except Exception as e:
        print(f"OpenRouter API error: {e}")
        return "Sorry, something went wrong."

@app.route("/", methods=["GET"])
def home():
    return "Facebook Chatbot with AI and memory is running!", 200

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
                            ai_reply = get_ai_reply(sender_id, user_message)
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
