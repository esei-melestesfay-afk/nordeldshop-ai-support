import os
import re
import requests
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from anthropic import Anthropic

app = Flask(__name__)
CORS(app)

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

LEAD_WEBHOOK_URL = os.environ.get("LEAD_WEBHOOK_URL")
STAFF_PASSWORD = os.environ.get("STAFF_PASSWORD", "nordeld2026")

CUSTOMER_SYSTEM_PROMPT = """
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

STAFF_SYSTEM_PROMPT = """
You are Nordeldshop's internal AI assistant for staff.

Your job is to help the business owner and staff work faster and smarter.

You can help with:
- Summarizing customer messages and leads.
- Deciding if a lead is hot, warm, or cold.
- Writing professional Swedish replies to customers.
- Suggesting the next best action.
- Improving customer support answers.
- Turning messy customer messages into clear tasks.
- Helping with sales, support, follow-up, and e-commerce communication.

Important rules:
- Always answer in Swedish.
- Be practical, clear, and business-focused.
- Do not invent facts about the store.
- If information is missing, say what is missing.
- Give useful output that staff can copy and use.
- Keep the tone professional but simple.

When analyzing a lead, use this structure:

1. Typ av ärende:
2. Prioritet:
3. Kort sammanfattning:
4. Vad kunden vill:
5. Rekommenderat nästa steg:
6. Förslag på svar till kunden:

Lead priority:
- Het lead = customer wants to buy now or wants direct contact.
- Varm lead = customer is interested but needs more information.
- Kall lead = general question, unclear interest, or low buying intent.
"""

CUSTOMER_HTML = """
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
        h2 { margin-top: 0; }
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

STAFF_HTML = """
<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <title>Nordeldshop Personal-AI</title>
    <style>
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #0f1115;
            color: #111;
        }

        .page {
            min-height: 100vh;
            padding: 40px 18px;
            background:
                radial-gradient(circle at top left, rgba(255,255,255,0.14), transparent 30%),
                linear-gradient(135deg, #111827, #050505);
        }

        .dashboard {
            max-width: 950px;
            margin: auto;
            background: #ffffff;
            border-radius: 22px;
            overflow: hidden;
            box-shadow: 0 25px 80px rgba(0,0,0,0.35);
        }

        .header {
            padding: 28px;
            background: #111;
            color: white;
        }

        .header h1 {
            margin: 0 0 8px;
            font-size: 28px;
        }

        .header p {
            margin: 0;
            color: #d1d5db;
            line-height: 1.5;
        }

        .content {
            padding: 24px;
        }

        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 18px;
            margin-bottom: 18px;
        }

        .card {
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            padding: 16px;
            background: #fafafa;
        }

        .card h3 {
            margin: 0 0 8px;
            font-size: 16px;
        }

        .card p {
            margin: 0;
            color: #555;
            font-size: 14px;
            line-height: 1.45;
        }

        label {
            display: block;
            font-weight: bold;
            margin-bottom: 8px;
        }

        input, textarea {
            width: 100%;
            box-sizing: border-box;
            border: 1px solid #d1d5db;
            border-radius: 14px;
            padding: 14px;
            font-size: 15px;
            font-family: Arial, sans-serif;
            outline: none;
        }

        textarea {
            min-height: 180px;
            resize: vertical;
            margin-bottom: 14px;
        }

        input {
            margin-bottom: 14px;
        }

        button {
            background: #111;
            color: white;
            border: none;
            border-radius: 14px;
            padding: 14px 20px;
            font-size: 15px;
            cursor: pointer;
            font-weight: bold;
        }

        button:hover {
            opacity: 0.9;
        }

        .output {
            margin-top: 20px;
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            padding: 18px;
            min-height: 120px;
            white-space: pre-wrap;
            line-height: 1.6;
        }

        .small {
            color: #666;
            font-size: 13px;
            margin-top: 10px;
        }

        @media (max-width: 750px) {
            .grid {
                grid-template-columns: 1fr;
            }
            .header h1 {
                font-size: 23px;
            }
        }
    </style>
</head>
<body>
    <div class="page">
        <div class="dashboard">
            <div class="header">
                <h1>Nordeldshop Personal-AI</h1>
                <p>Privat AI-assistent för leads, kundsvar, support och försäljning.</p>
            </div>

            <div class="content">
                <div class="grid">
                    <div class="card">
                        <h3>Analysera leads</h3>
                        <p>Klistra in en kunds meddelande och få prioritet, sammanfattning och nästa steg.</p>
                    </div>
                    <div class="card">
                        <h3>Skriv kundsvar</h3>
                        <p>Få ett professionellt svenskt svar som du kan kopiera till mejl eller support.</p>
                    </div>
                </div>

                <label>Lösenord</label>
                <input id="password" type="password" placeholder="Skriv personal-lösenord..." />

                <label>Vad vill du att AI:n ska hjälpa dig med?</label>
                <textarea id="staffQuestion" placeholder="Exempel: Analysera denna lead och skriv ett svar: Sara, sara@gmail.com, jag vill köpa men undrar leveranstiden."></textarea>

                <button onclick="askStaffAI()">Analysera med AI</button>

                <div class="small">
                    Tips: Klistra in kundens fråga, lead-information eller ett mejl du vill svara på.
                </div>

                <div id="staffOutput" class="output">AI-svaret visas här...</div>
            </div>
        </div>
    </div>

    <script>
        async function askStaffAI() {
            const password = document.getElementById("password").value;
            const question = document.getElementById("staffQuestion").value;
            const output = document.getElementById("staffOutput");

            if (!password.trim() || !question.trim()) {
                output.textContent = "Skriv både lösenord och fråga först.";
                return;
            }

            output.textContent = "AI analyserar...";

            try {
                const response = await fetch("/staff-ask", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        password: password,
                        question: question
                    })
                });

                const data = await response.json();
                output.textContent = data.answer;
            } catch (error) {
                output.textContent = "Något gick fel. Försök igen.";
            }
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

def extract_name(text, email):
    name = text.replace(email, "")
    name = name.replace(",", "")
    name = name.replace("Namn:", "")
    name = name.replace("namn:", "")
    name = name.strip()

    if not name:
        return "Okänt namn"

    return name

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
        "information",
        "kan någon kontakta",
        "jag behöver hjälp",
        "jag har en fråga innan köp",
        "jag vill prata",
        "kan ni höra av er"
    ]
    return any(word in text_lower for word in lead_words)

def send_lead_to_google_sheets(customer_message, customer_email):
    if not LEAD_WEBHOOK_URL:
        print("ERROR: Missing LEAD_WEBHOOK_URL")
        return False, "Missing LEAD_WEBHOOK_URL"

    customer_name = extract_name(customer_message, customer_email)

    lead_data = {
        "name": customer_name,
        "email": customer_email,
        "message": customer_message,
        "source": "AI-chatten på Nordeldshop"
    }

    try:
        response = requests.post(
            LEAD_WEBHOOK_URL,
            data=lead_data,
            timeout=20,
            allow_redirects=True
        )

        print("GOOGLE SHEETS STATUS:", response.status_code)
        print("GOOGLE SHEETS RESPONSE:", response.text[:500])

        if response.status_code in [200, 201, 202, 302]:
            return True, "Lead sent to Google Sheets."

        if "success" in response.text.lower() or "true" in response.text.lower():
            return True, "Lead sent to Google Sheets."

        return False, f"Google Sheets webhook error: {response.status_code} - {response.text[:200]}"

    except Exception as e:
        print("GOOGLE SHEETS ERROR:", str(e))
        return False, str(e)

@app.route("/")
def home():
    return render_template_string(CUSTOMER_HTML)

@app.route("/staff")
def staff():
    return render_template_string(STAFF_HTML)

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question", "")

    if looks_like_email(question):
        customer_email = extract_email(question)
        success, result = send_lead_to_google_sheets(question, customer_email)

        print("LEAD RESULT:", result)

        if success:
            return jsonify({
                "answer": "Tack! Vi har tagit emot dina uppgifter och återkommer så snart vi kan."
            })
        else:
            return jsonify({
                "answer": "Jag kunde inte spara uppgifterna just nu. Kontakta gärna supporten direkt."
            })

    if looks_like_lead_request(question):
        return jsonify({
            "answer": "Absolut! Skriv gärna ditt namn och din mejladress så hjälper vi dig vidare."
        })

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=300,
        system=CUSTOMER_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": question}
        ]
    )

    answer = message.content[0].text
    return jsonify({"answer": answer})

@app.route("/staff-ask", methods=["POST"])
def staff_ask():
    data = request.get_json()
    password = data.get("password", "")
    question = data.get("question", "")

    if password != STAFF_PASSWORD:
        return jsonify({
            "answer": "Fel lösenord. Du har inte åtkomst till personal-AI:n."
        })

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=700,
        system=STAFF_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": question}
        ]
    )

    answer = message.content[0].text
    return jsonify({"answer": answer})

if __name__ == "__main__":
    app.run(debug=True)