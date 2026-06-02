import os
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from anthropic import Anthropic

app = Flask(__name__)
CORS(app)
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """
You are a customer support assistant for Nordeldshop, a Swedish Shopify store.

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

Rules:
- Always answer in Swedish.
- Answer short, clear, and friendly.
- Help with delivery, returns, products, payments, order tracking, and contact questions.
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
        h2 {
            margin-top: 0;
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

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question", "")

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