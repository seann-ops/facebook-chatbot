from flask import Flask, request
import os
import requests
from collections import defaultdict

# ------------------------
# App Initialization
# ------------------------
app = Flask(__name__)

# ------------------------
# Configuration
# ------------------------
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySuperSecretToken")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# Conversation history: stores alternating user and bot messages
conversation_history = defaultdict(list)

# ------------------------
# Facebook Send Message
# ------------------------
def send_message(recipient_id, message_text):
    """
    Sends a text message to a Facebook Messenger user.
    """
    if not PAGE_ACCESS_TOKEN:
        print("❌ PAGE_ACCESS_TOKEN not set.")
        return

    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }

    try:
        response = requests.post(
            "https://graph.facebook.com/v18.0/me/messages",
            params=params, headers=headers, json=data
        )
        print(f"📤 Sent message to {recipient_id}: {message_text}")
        print(f"[FB API] {response.status_code} - {response.text}")

    except Exception as e:
        print(f"[❌ Exception] Sending FB message failed: {e}")

# ------------------------
# AI Reply Function (non-streaming for stability)
# ------------------------
def get_ai_reply(user_id, user_message):
    """
    Sends conversation history + latest user message to OpenRouter API
    and returns the AI's reply.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    system_prompt = "You are a helpful assistant."
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation memory
    for i, msg in enumerate(conversation_history[user_id]):
        role = "user" if i % 2 == 0 else "assistant"
        messages.append({"role": role, "content": msg})

    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": "openchat/openchat-7b:free",  # stable free model
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 200,
        "stream": False
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"[❌ OpenRouter Error] {response.status_code}: {response.text}")
            return "Sorry, I couldn't get a reply from AI service."

        data = response.json()
        print(f"[AI Raw Response] {data}")

        ai_text = data["choices"][0]["message"]["content"]

        # Save history (last 10 turns)
        conversation_history[user_id].append(user_message)
        conversation_history[user_id].append(ai_text)
        conversation_history[user_id] = conversation_history[user_id][-10:]

        return ai_text

    except Exception as e:
        print(f"[❌ Exception] OpenRouter API failed: {e}")
        return "Sorry, something went wrong."

# ------------------------
# Routes
# ------------------------
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
                            ai_reply = get_ai_reply(sender_id, user_message)
                            send_message(sender_id, ai_reply)
                        else:
                            send_message(sender_id, "Thanks for sending me something!")
        return "EVENT_RECEIVED", 200

# ------------------------
# Main
# ------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
