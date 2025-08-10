from flask import Flask, request
import os
import requests
from collections import defaultdict

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySuperSecretToken")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
HF_API_KEY = os.environ.get("HF_API_KEY")

# Store conversation history per user
conversation_history = defaultdict(list)

def get_ai_reply(user_id, user_message):
    # Updated to use a publicly hosted model on Hugging Face
    API_URL = "https://api-inference.huggingface.co/models/gpt2"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}

    # Append user's message to history
    conversation_history[user_id].append(user_message)

    # Keep only last 5 exchanges (10 messages)
    if len(conversation_history[user_id]) > 10:
        conversation_history[user_id] = conversation_history[user_id][-10:]

    # Combine conversation into one string (for GPT-2, we just send last message)
    # GPT-2 doesn't support dialogue history by default in the API, so just send current message
    prompt = user_message

    payload = {"inputs": prompt}

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        print(f"HF API status code: {response.status_code}")
        print(f"HF API raw response text: {response.text}")

        if response.status_code != 200:
            print(f"Error: HF API returned status code {response.status_code}")
            return "Sorry, I couldn't get a reply from AI service."

        if not response.text:
            print("Error: HF API returned empty response")
            return "Sorry, I couldn't get a reply from AI service."

        data = response.json()

        # GPT-2 returns a list of generated sequences in 'generated_text'
        if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
            ai_text = data[0]["generated_text"]

            # Append AI reply to history
            conversation_history[user_id].append(ai_text)

            return ai_text
        else:
            print("Unexpected HF API response structure:", data)
            return "Sorry, I couldn't think of a reply."

    except Exception as e:
        print(f"AI API error: {e}")
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
