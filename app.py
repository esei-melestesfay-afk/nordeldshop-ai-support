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
DASHBOARD_WEBHOOK_URL = os.environ.get("DASHBOARD_WEBHOOK_URL")
DASHBOARD_WEBHOOK_SECRET = os.environ.get("DASHBOARD_WEBHOOK_SECRET")
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
You are Nordeldshop's internal AI business assistant for staff.

Your job is to help the business owner and staff work faster, smarter, and more professionally.

You can help with:
- Summarizing customer messages and leads.
- Deciding if a customer is a hot sales lead, warm lead, cold lead, support case, or complaint.
- Writing professional Swedish replies to customers.
- Suggesting the next best action.
- Improving customer support answers.
- Turning messy customer messages into clear tasks.
- Helping with sales, support, follow-up, e-commerce communication, and customer retention.

Important rules:
- Always answer in Swedish.
- Be practical, clear, and business-focused.
- Do not invent facts about the store.
- If information is missing, say what is missing.
- Give useful output that staff can copy and use.
- Keep the tone professional but simple.
- If it is a complaint or broken product issue, do NOT call it a hot lead. Call it "Hög prioritet – reklamation/support".
- If the customer wants to buy now, call it "Het säljlead".
- If the customer is interested but unsure, call it "Varm lead".
- If it is only a general question, call it "Kall lead" or "Vanligt supportärende".

Use this structure when useful:

1. Typ av ärende:
2. Prioritet:
3. Kort sammanfattning:
4. Vad kunden vill:
5. Rekommenderat nästa steg:
6. Förslag på svar till kunden:

Make the final customer reply clean, friendly, and ready to copy.
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

            messages.innerHTML += '<div class="user">Du: ' + question + '</div>';
            input.value = "";

            const response = await fetch("/ask", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({question: question})
            });

            const data = await response.json();
            messages.innerHTML += '<div class="bot">Support: ' + data.answer + '</div>';
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
    <title>Nordeldshop Command Center</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <style>
        * {
            box-sizing: border-box;
        }

        :root {
            --bg: #060816;
            --panel: rgba(15, 23, 42, 0.78);
            --panel2: rgba(255, 255, 255, 0.075);
            --line: rgba(255,255,255,0.12);
            --text: #f8fafc;
            --muted: #9ca3af;
            --blue: #3b82f6;
            --purple: #8b5cf6;
            --green: #22c55e;
            --orange: #f59e0b;
            --red: #ef4444;
        }

        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
        }

        .page {
            min-height: 100vh;
            padding: 26px;
            background:
                radial-gradient(circle at 12% 8%, rgba(59, 130, 246, 0.35), transparent 28%),
                radial-gradient(circle at 88% 18%, rgba(139, 92, 246, 0.35), transparent 30%),
                radial-gradient(circle at 50% 95%, rgba(34, 197, 94, 0.16), transparent 30%),
                linear-gradient(135deg, #060816, #101827 60%, #030712);
        }

        .shell {
            max-width: 1220px;
            margin: 0 auto;
        }

        .topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 18px;
            margin-bottom: 22px;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .logo {
            width: 52px;
            height: 52px;
            border-radius: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, var(--blue), var(--purple));
            box-shadow: 0 16px 45px rgba(59,130,246,0.36);
            font-size: 25px;
        }

        .brand h1 {
            margin: 0;
            font-size: 22px;
            letter-spacing: -0.5px;
        }

        .brand p {
            margin: 4px 0 0;
            color: var(--muted);
            font-size: 13px;
        }

        .status-row {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        .pill {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 13px;
            border-radius: 999px;
            background: rgba(255,255,255,0.08);
            border: 1px solid var(--line);
            color: #dbeafe;
            font-size: 13px;
            backdrop-filter: blur(14px);
        }

        .dot {
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: var(--green);
            box-shadow: 0 0 20px var(--green);
        }

        .login-wrap {
            max-width: 500px;
            margin: 75px auto 0;
        }

        .login-card, .panel, .stat-card {
            background: var(--panel);
            border: 1px solid var(--line);
            box-shadow: 0 30px 100px rgba(0,0,0,0.46);
            backdrop-filter: blur(22px);
        }

        .login-card {
            border-radius: 30px;
            padding: 32px;
            position: relative;
            overflow: hidden;
        }

        .login-card:before {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(135deg, rgba(59,130,246,0.18), rgba(139,92,246,0.14), transparent);
            pointer-events: none;
        }

        .login-inner {
            position: relative;
        }

        .lock-icon {
            width: 58px;
            height: 58px;
            border-radius: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(255,255,255,0.09);
            border: 1px solid var(--line);
            font-size: 28px;
            margin-bottom: 18px;
        }

        .login-card h2 {
            margin: 0 0 10px;
            font-size: 31px;
            letter-spacing: -0.9px;
        }

        .login-card p {
            margin: 0 0 24px;
            color: #b8c1d6;
            line-height: 1.55;
        }

        label {
            display: block;
            margin-bottom: 8px;
            font-size: 14px;
            font-weight: 800;
            color: #e5e7eb;
        }

        .input, .textarea {
            width: 100%;
            border: 1px solid rgba(255,255,255,0.13);
            background: rgba(255,255,255,0.08);
            color: white;
            border-radius: 17px;
            padding: 15px 16px;
            font-size: 15px;
            outline: none;
            transition: 0.18s;
        }

        .input:focus, .textarea:focus {
            border-color: #60a5fa;
            box-shadow: 0 0 0 4px rgba(96,165,250,0.16);
        }

        .input::placeholder, .textarea::placeholder {
            color: #7b8497;
        }

        .btn {
            border: none;
            border-radius: 17px;
            padding: 15px 18px;
            background: linear-gradient(135deg, #2563eb, #7c3aed);
            color: white;
            font-weight: 900;
            font-size: 15px;
            cursor: pointer;
            transition: 0.18s;
            box-shadow: 0 16px 42px rgba(37,99,235,0.34);
        }

        .btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 20px 48px rgba(124,58,237,0.43);
        }

        .btn:active {
            transform: translateY(0);
        }

        .btn-secondary {
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.13);
            box-shadow: none;
        }

        .btn-green {
            background: linear-gradient(135deg, #16a34a, #22c55e);
            box-shadow: 0 16px 42px rgba(34,197,94,0.25);
        }

        .login-btn {
            width: 100%;
            margin-top: 14px;
        }

        .error {
            min-height: 20px;
            color: #fecaca;
            font-size: 14px;
            margin-top: 12px;
        }

        .dashboard {
            display: none;
            animation: fadeIn 0.35s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: none; }
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 14px;
            margin-bottom: 18px;
        }

        .stat-card {
            border-radius: 22px;
            padding: 18px;
        }

        .stat-card .icon {
            width: 42px;
            height: 42px;
            border-radius: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(255,255,255,0.09);
            border: 1px solid var(--line);
            margin-bottom: 14px;
            font-size: 20px;
        }

        .stat-card h3 {
            margin: 0;
            font-size: 21px;
        }

        .stat-card p {
            margin: 5px 0 0;
            color: var(--muted);
            font-size: 13px;
        }

        .main-grid {
            display: grid;
            grid-template-columns: 1.2fr 0.8fr;
            gap: 18px;
        }

        .panel {
            border-radius: 30px;
            overflow: hidden;
        }

        .panel-head {
            padding: 22px 24px;
            border-bottom: 1px solid var(--line);
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 14px;
        }

        .panel-head h2 {
            margin: 0;
            font-size: 25px;
            letter-spacing: -0.7px;
        }

        .panel-head p {
            margin: 5px 0 0;
            color: var(--muted);
            font-size: 13px;
        }

        .panel-body {
            padding: 24px;
        }

        .textarea {
            min-height: 240px;
            resize: vertical;
            line-height: 1.55;
        }

        .actions {
            display: flex;
            gap: 11px;
            flex-wrap: wrap;
            margin-top: 14px;
        }

        .output {
            margin-top: 18px;
            min-height: 250px;
            background: rgba(2,6,23,0.72);
            border: 1px solid rgba(255,255,255,0.10);
            border-radius: 23px;
            padding: 20px;
            color: #e5e7eb;
            white-space: pre-wrap;
            line-height: 1.65;
            font-size: 15px;
            position: relative;
            overflow: hidden;
        }

        .output.loading:before {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.04), transparent);
            animation: shimmer 1.3s infinite;
        }

        @keyframes shimmer {
            from { transform: translateX(-100%); }
            to { transform: translateX(100%); }
        }

        .side {
            display: grid;
            gap: 18px;
        }

        .feature-list {
            display: grid;
            gap: 12px;
        }

        .feature {
            display: flex;
            gap: 12px;
            padding: 15px;
            border-radius: 20px;
            background: rgba(255,255,255,0.07);
            border: 1px solid rgba(255,255,255,0.10);
        }

        .feature .ficon {
            width: 42px;
            height: 42px;
            border-radius: 15px;
            flex: 0 0 auto;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, rgba(59,130,246,0.35), rgba(139,92,246,0.35));
            font-size: 20px;
        }

        .feature h3 {
            margin: 0 0 5px;
            font-size: 15px;
        }

        .feature p {
            margin: 0;
            color: var(--muted);
            line-height: 1.4;
            font-size: 13px;
        }

        .prompt-list {
            display: grid;
            gap: 10px;
        }

        .prompt {
            text-align: left;
            width: 100%;
            border: 1px solid rgba(255,255,255,0.10);
            background: rgba(255,255,255,0.06);
            color: #dbeafe;
            border-radius: 16px;
            padding: 13px;
            cursor: pointer;
            line-height: 1.35;
            font-size: 13px;
            transition: 0.16s;
        }

        .prompt:hover {
            background: rgba(59,130,246,0.16);
            border-color: rgba(96,165,250,0.35);
        }

        .toast {
            position: fixed;
            right: 22px;
            bottom: 22px;
            background: rgba(15,23,42,0.92);
            border: 1px solid var(--line);
            color: white;
            padding: 13px 16px;
            border-radius: 16px;
            box-shadow: 0 18px 55px rgba(0,0,0,0.35);
            display: none;
            z-index: 99;
        }

        .small {
            color: var(--muted);
            font-size: 13px;
            line-height: 1.5;
            margin-top: 12px;
        }

        @media (max-width: 980px) {
            .stats {
                grid-template-columns: repeat(2, 1fr);
            }

            .main-grid {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 620px) {
            .page {
                padding: 16px;
            }

            .topbar {
                flex-direction: column;
                align-items: flex-start;
            }

            .status-row {
                width: 100%;
            }

            .stats {
                grid-template-columns: 1fr;
            }

            .panel-head {
                align-items: flex-start;
                flex-direction: column;
            }

            .login-card {
                padding: 24px;
                border-radius: 24px;
            }

            .login-card h2 {
                font-size: 26px;
            }
        }
    </style>
</head>

<body>
    <div class="page">
        <div class="shell">
            <div class="topbar">
                <div class="brand">
                    <div class="logo">⚡</div>
                    <div>
                        <h1>Nordeldshop Command Center</h1>
                        <p>AI-dashboard för support, leads och kundsvar</p>
                    </div>
                </div>

                <div class="status-row">
                    <div class="pill"><span class="dot"></span> System online</div>
                    <div class="pill">🔒 Privat personalyta</div>
                </div>
            </div>

            <div id="loginCard" class="login-wrap">
                <div class="login-card">
                    <div class="login-inner">
                        <div class="lock-icon">🔐</div>
                        <h2>Personalåtkomst</h2>
                        <p>Logga in för att öppna Nordeldshops interna AI-assistent. Här kan du analysera leads, skriva kundsvar och få rekommenderade nästa steg.</p>

                        <label>Lösenord</label>
                        <input id="loginPassword" class="input" type="password" placeholder="Skriv personal-lösenord..." />

                        <button class="btn login-btn" onclick="unlockDashboard()">Öppna Command Center</button>
                        <div id="loginError" class="error"></div>
                    </div>
                </div>
            </div>

            <div id="dashboard" class="dashboard">
                <div class="stats">
                    <div class="stat-card">
                        <div class="icon">🔥</div>
                        <h3>Leadanalys</h3>
                        <p>Hitta heta, varma och kalla leads.</p>
                    </div>
                    <div class="stat-card">
                        <div class="icon">✉️</div>
                        <h3>Kundsvar</h3>
                        <p>Skriv färdiga svar på svenska.</p>
                    </div>
                    <div class="stat-card">
                        <div class="icon">🧠</div>
                        <h3>AI-stöd</h3>
                        <p>Sammanfatta och strukturera ärenden.</p>
                    </div>
                    <div class="stat-card">
                        <div class="icon">⚙️</div>
                        <h3>Nästa steg</h3>
                        <p>Få tydliga actions för varje kund.</p>
                    </div>
                </div>

                <div class="main-grid">
                    <div class="panel">
                        <div class="panel-head">
                            <div>
                                <h2>AI-assistent</h2>
                                <p>Klistra in kundtext, lead, mejl eller supportärende.</p>
                            </div>
                            <div class="pill">✨ Claude API</div>
                        </div>

                        <div class="panel-body">
                            <label>Kundmeddelande eller uppgift</label>
                            <textarea id="staffQuestion" class="textarea" placeholder="Exempel:
Analysera denna lead och skriv ett svar:
Sara, sara@gmail.com
Jag vill köpa men undrar hur lång leveransen är."></textarea>

                            <div class="actions">
                                <button class="btn" onclick="askStaffAI()">Analysera med AI</button>
                                <button class="btn btn-green" onclick="copyOutput()">Kopiera svar</button>
                                <button class="btn btn-secondary" onclick="clearAll()">Rensa</button>
                            </div>

                            <div id="staffOutput" class="output">AI-svaret visas här...</div>
                            <div class="small">Tips: Använd snabbkommandon till höger för att få rätt typ av AI-svar direkt.</div>
                        </div>
                    </div>

                    <div class="side">
                        <div class="panel">
                            <div class="panel-head">
                                <div>
                                    <h2>Funktioner</h2>
                                    <p>Byggt för praktisk kundsupport.</p>
                                </div>
                            </div>

                            <div class="panel-body">
                                <div class="feature-list">
                                    <div class="feature">
                                        <div class="ficon">📌</div>
                                        <div>
                                            <h3>Prioritering</h3>
                                            <p>AI:n avgör om ärendet är sälj, support, reklamation eller låg prioritet.</p>
                                        </div>
                                    </div>

                                    <div class="feature">
                                        <div class="ficon">💬</div>
                                        <div>
                                            <h3>Färdiga svar</h3>
                                            <p>Du får ett professionellt svar som kan kopieras direkt till kunden.</p>
                                        </div>
                                    </div>

                                    <div class="feature">
                                        <div class="ficon">🚀</div>
                                        <div>
                                            <h3>Nästa steg</h3>
                                            <p>AI:n berättar vad du bör göra: svara, be om ordernummer, bild eller följa upp.</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="panel">
                            <div class="panel-head">
                                <div>
                                    <h2>Snabbkommandon</h2>
                                    <p>Klicka och fyll på med kundens text.</p>
                                </div>
                            </div>

                            <div class="panel-body">
                                <div class="prompt-list">
                                    <button class="prompt" onclick="setPrompt('Analysera denna lead och skriv ett professionellt svar:\\n')">🔥 Analysera lead + skriv svar</button>
                                    <button class="prompt" onclick="setPrompt('Skriv ett lugnt och professionellt svar till en missnöjd kund:\\n')">🛡️ Svara missnöjd kund</button>
                                    <button class="prompt" onclick="setPrompt('Sammanfatta detta kundmeddelande och ge nästa steg:\\n')">🧠 Sammanfatta ärende</button>
                                    <button class="prompt" onclick="setPrompt('Förbättra detta kundsvar så det låter professionellt men enkelt:\\n')">✨ Förbättra kundsvar</button>
                                    <button class="prompt" onclick="setPrompt('Skriv ett uppföljningsmejl till denna kund:\\n')">📩 Skriv uppföljningsmejl</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div id="toast" class="toast">Kopierat!</div>
    </div>

    <script>
        let savedPassword = "";

        function showToast(text) {
            const toast = document.getElementById("toast");
            toast.textContent = text;
            toast.style.display = "block";
            setTimeout(function() {
                toast.style.display = "none";
            }, 1800);
        }

        async function unlockDashboard() {
            const password = document.getElementById("loginPassword").value;
            const error = document.getElementById("loginError");

            if (!password.trim()) {
                error.textContent = "Skriv lösenord först.";
                return;
            }

            error.textContent = "Kontrollerar lösenord...";

            try {
                const response = await fetch("/staff-login", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({password: password})
                });

                const data = await response.json();

                if (!data.success) {
                    error.textContent = "Fel lösenord. Försök igen.";
                    return;
                }

                savedPassword = password;
                sessionStorage.setItem("staffPassword", password);

                document.getElementById("loginCard").style.display = "none";
                document.getElementById("dashboard").style.display = "block";
                showToast("Välkommen till Command Center");
            } catch (err) {
                error.textContent = "Något gick fel. Försök igen.";
            }
        }

        function setPrompt(text) {
            const textarea = document.getElementById("staffQuestion");
            textarea.value = text;
            textarea.focus();
        }

        async function askStaffAI() {
            const question = document.getElementById("staffQuestion").value;
            const output = document.getElementById("staffOutput");

            if (!savedPassword.trim() || !question.trim()) {
                output.textContent = "Skriv både lösenord och fråga först.";
                return;
            }

            output.classList.add("loading");
            output.textContent = "AI analyserar ärendet...";

            try {
                const response = await fetch("/staff-ask", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        password: savedPassword,
                        question: question
                    })
                });

                const data = await response.json();
                output.classList.remove("loading");
                output.textContent = data.answer;
            } catch (error) {
                output.classList.remove("loading");
                output.textContent = "Något gick fel. Försök igen.";
            }
        }

        function copyOutput() {
            const output = document.getElementById("staffOutput").textContent;
            navigator.clipboard.writeText(output);
            showToast("AI-svaret kopierades");
        }

        function clearAll() {
            document.getElementById("staffQuestion").value = "";
            document.getElementById("staffOutput").textContent = "AI-svaret visas här...";
            showToast("Rensat");
        }

        document.getElementById("loginPassword").addEventListener("keydown", function(event) {
            if (event.key === "Enter") {
                unlockDashboard();
            }
        });

        window.addEventListener("load", function() {
            const storedPassword = sessionStorage.getItem("staffPassword");
            if (storedPassword) {
                savedPassword = storedPassword;
                document.getElementById("loginCard").style.display = "none";
                document.getElementById("dashboard").style.display = "block";
            }
        });
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


def send_lead_to_dashboard(customer_message, customer_email):
    if not DASHBOARD_WEBHOOK_URL or not DASHBOARD_WEBHOOK_SECRET:
        print("ERROR: Missing dashboard webhook settings")
        return False, "Missing dashboard webhook settings"

    customer_name = extract_name(customer_message, customer_email)

    lead_data = {
        "secret": DASHBOARD_WEBHOOK_SECRET,
        "name": customer_name,
        "email": customer_email,
        "message": customer_message,
        "source": "Nordeldshop AI-chatten"
    }

    try:
        response = requests.post(
            DASHBOARD_WEBHOOK_URL,
            json=lead_data,
            timeout=20
        )

        print("DASHBOARD STATUS:", response.status_code)
        print("DASHBOARD RESPONSE:", response.text[:500])

        if response.status_code in [200, 201, 202]:
            return True, "Lead sent to Fostira Dashboard."

        return False, f"Dashboard webhook error: {response.status_code} - {response.text[:200]}"

    except Exception as e:
        print("DASHBOARD ERROR:", str(e))
        return False, str(e)


@app.route("/")
def home():
    return render_template_string(CUSTOMER_HTML)


@app.route("/staff")
def staff():
    return render_template_string(STAFF_HTML)


@app.route("/staff-login", methods=["POST"])
def staff_login():
    data = request.get_json()
    password = data.get("password", "")

    if password == STAFF_PASSWORD:
        return jsonify({"success": True})

    return jsonify({"success": False})


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question", "")

    if looks_like_email(question):
        customer_email = extract_email(question)

        sheets_success, sheets_result = send_lead_to_google_sheets(question, customer_email)
        dashboard_success, dashboard_result = send_lead_to_dashboard(question, customer_email)

        print("GOOGLE SHEETS RESULT:", sheets_result)
        print("DASHBOARD RESULT:", dashboard_result)

        if sheets_success or dashboard_success:
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
        max_tokens=900,
        system=STAFF_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": question}
        ]
    )

    answer = message.content[0].text
    return jsonify({"answer": answer})


if __name__ == "__main__":
    app.run(debug=True)