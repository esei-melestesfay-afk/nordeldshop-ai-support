import os
import re
import smtplib
from email.message import EmailMessage
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from anthropic import Anthropic

app = Flask(__name__)
CORS(app)

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
LEAD_RECEIVER_EMAIL = os.environ.get("LEAD_RECEIVER_EMAIL")


SYSTEM_PROMPT = """
You are a customer support assistant for Nordeldshop, a Swedish Shopify store.

Your job:
- Help customers with delivery, tracking, returns, payments, products, order questions, and contact questions.
- If a customer seems interested in buying, wants help, wants to be contacted, or asks for more information, ask for their name and email address.
- Always answer in Swedish.

Store information:
- Store name: Nordeldshop
- Platform: Shopify
- Store language: Swedish
- Delivery time: 7–15 arbetsdagar
- Tracking: Customers receive tracking information by email when the order has been shipped.
- If the customer asks about a specific order, ask for their order number and email address.
- If you do not know the answer, tell the customer to contact support.
- Do not invent information.
- Do not promise exact delivery dates.

Lead rules:
- If the customer wants to be contacted, asks for personal help, or seems like a potential buyer, ask:
  "Absolut! Skriv gärna ditt namn och din mejladress så hjälper vi dig vidare."
- Do not say that you have saved their information unless the system confirms it.

Style rules:
- Always answer in Swedish.
- Answer short, clear, and friendly.
- Do not use too many emojis.
"""


HTML = """
<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <title>Nordeldshop AI-support</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f4f4f4;
            padding: 40px;
        }
        .chatbox {
            max-width: 600px;
            margin: auto;
            background: white;
            border-radius: 14px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
        #messages {
            min-height: 250px;
            border: 1px solid #ddd;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
            background: #fafafa;
        }
        .user {
            font-weight: bold;
            margin-top: 10px;
        }
        .bot {
            margin-bottom: 10px;
        }
        input {
            width: 75%;
            padding: 12px;
            border-radius: 8px;
            border: 1px solid #ccc;
        }
        button {
            padding: 12px 18px;
            border: none;
            border-radius: 8px;
            background: black;
            color: white;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="chatbox">
        <h2>Nordeldshop AI-support</h2>
        <p>Ställ en fråga om leverans, spårning eller retur.</p>

        <div id="messages"></div>

        <input id="question" placeholder="Skriv din fråga här..." />
        <button onclick="sendMessage()">Skicka</button>
    </div>

    <script>
        async function sendMessage() {
            const input = document.getElementById("question");
            const messages = document.getElementById("messages");
            const question = input.value;

            if (!question.trim()) return;

            messages.innerHTML += `<div class="user">Du: ${question}</div>`;
            input.value = "";

            const response = await fetch("/ask", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({question: question})
            });

            const data = await response.json();
            messages.innerHTML += `<div class="bot">Support: ${data.answer}</div>`;
        }
    </script>
</body>
</html>
"""


def looks_like_email(text):
    return re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text) is not None


def extract_email(text):
    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    return match.group(0) if match else None


def looks_like_lead_request(text):
    text_lower = text.lower()
    lead_words = [
        "kontakta mig",
        "ring mig",
        "mejla mig",
        "jag vill bli kontaktad",
        "jag är intresserad",
        "vill veta mer",
        "kan ni hjälpa mig",
        "jag vill köpa",
        "hjälp mig",
        "mer info",
        "information"
    ]
    return any(word in text_lower for word in lead_words)


def send_lead_email(customer_message, customer_email):
    if not EMAIL_USER or not EMAIL_PASSWORD or not LEAD_RECEIVER_EMAIL:
        return False, "Email settings are missing."

    subject = "Ny lead från Nordeldshop AI-support"

    body = f"""
Ny lead från Nordeldshop AI-support

Kundens meddelande:
{customer_message}

Kundens e-post:
{customer_email}

Källa:
AI-chatten på Nordeldshop
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = LEAD_RECEIVER_EMAIL
    msg.set_content(body)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as smtp:
    smtp.starttls()
    smtp.login(EMAIL_USER, EMAIL_PASSWORD)
    smtp.send_message(msg)
        return True, "Lead email sent."
    except Exception as e:
        return False, str(e)


@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question", "")

    if looks_like_email(question):
        customer_email = extract_email(question)
        success, result = send_lead_email(question, customer_email)

        if success:
            return jsonify({
                "answer": "Tack! Vi har tagit emot dina uppgifter och återkommer så snart vi kan."
            })
        else:
            return jsonify({
                "answer": "Jag kunde inte skicka uppgifterna just nu. Kontakta gärna supporten direkt."
            })

    if looks_like_lead_request(question):
        return jsonify({
            "answer": "Absolut! Skriv gärna ditt namn och din mejladress så hjälper vi dig vidare."
        })

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": question}
        ]
    )

    answer = message.content[0].text
    return jsonify({"answer": answer})


if __name__ == "__main__":
    app.run(debug=True)