from flask import Flask, request
import os
import requests
from collections import defaultdict
import json

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
# AI Reply Function (Streaming)
# ------------------------
def get_ai_reply(user_id, user_message):
    """
    Sends conversation history + latest user message to OpenRouter API
    and streams the AI's reply token-by-token to Facebook Messenger.
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
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 150,
        "stream": True
    }

    try:
        with requests.post(url, headers=headers, json=payload, stream=True) as r:
            if r.status_code != 200:
                print(f"[❌ OpenRouter Error] {r.status_code}: {r.text}")
                send_message(user_id, "Sorry, I couldn't get a reply from AI service.")
                return

            partial_reply = ""
            for line in r.iter_lines():
                if line:
                    try:
                        # Each streamed line starts with 'data: '
                        if line.startswith(b"data: "):
                            line_data = line[6:].decode("utf-8")
                            if line_data.strip() == "[DONE]":
                                break
                            event = json.loads(line_data)
                            delta = event["choices"][0]["delta"].get("content", "")
                            if delta:
                                partial_reply += delta
                                send_message(user_id, partial_reply)
                    except Exception as e:
                        print(f"[⚠️ Stream Error] {e}")

            # Save to history after stream ends
            conversation_history[user_id].append(user_message)
            conversation_history[user_id].append(partial_reply)
            conversation_history[user_id] = conversation_history[user_id][-10:]

    except Exception as e:
        print(f"[❌ Exception] OpenRouter API streaming failed: {e}")
        send_message(user_id, "Sorry, something went wrong.")

# ------------------------
# Routes
# ------------------------
@app.route("/", methods=["GET"])
def home():
    return "Facebook Chatbot with AI (Streaming) is running!", 200

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
                            get_ai_reply(sender_id, user_message)
                        else:
                            send_message(sender_id, "Thanks for sending me something!")
        return "EVENT_RECEIVED", 200

# ------------------------
# Main
# ------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
