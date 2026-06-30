# Emperor Nexus Authority (E.N.A.) — Matrimony AI Chatbot

An intelligent AI assistant by **Emperor Nexus Authority (E.N.A.)** that connects to your MySQL matrimony database and answers user questions using Groq's free LLM (Llama 3).

## How It Works

```
User question → Intent detection → SQL query → Database → LLM → Natural reply
```

The chatbot:
1. Detects what the user is asking (pricing, profiles, support, etc.)
2. Queries your live MySQL database for relevant data
3. Sends the data to Groq's Llama 3 70B (free) for a natural language response

## Features

- **Membership Plans** — Query `membershipplan` table for pricing, duration, features
- **Profile Search** — Search `register` table by gender, age, city, religion, caste, marital status
- **FAQs** — Answers from CMS help pages
- **Success Stories** — Share testimonials (from `successstory` / `testimonial` tables)
- **Support** — Contact details from `siteconfig` and CMS
- **About / Safety / Refund** — Content from CMS pages
- **Fallback** — Combines multiple data sources for general questions

## Prerequisites

- Python 3.10+
- MySQL database (remote or local)
- Free Groq API key from https://console.groq.com

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

Copy `.env.example` and fill in:

```bash
# Database
DB_HOST=your-db-host.com
DB_PORT=3306
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=your_db_name

# Groq (free)
GROQ_API_KEY=gsk_your_key_here
```

### 3. Run the Backend

```bash
python matrimony_chatbot.py
```

Server starts at **http://localhost:8000**

### 4. Open the Chat UI

Open `index.html` in your browser.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Server status |
| `/health` | GET | Health check (DB + API) |
| `/chat` | POST | Send a message `{"message": "..."}` |

## Project Structure

```
├── matrimony_chatbot.py   # FastAPI backend (DB + LLM)
├── index.html             # Chat UI (open in browser)
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variable template
├── sys_dbconnection.php   # Your DB connection file
└── README.md              # This file
```

## Deployment

**On your web server** (for production):

```bash
nohup python matrimony_chatbot.py > chatbot.log 2>&1 &
```

Or use a process manager like `pm2` or `supervisor`.

**Update the API URL** in `index.html`:
```js
const API_URL = 'https://your-domain.com/chat';
```

## Customization

- **Add more intent keywords** — Edit `INTENT_MAP` in `matrimony_chatbot.py`
- **Add more cities/castes** — Edit `CITIES` / `CASTE_KEYWORDS` lists
- **Change LLM model** — Edit the `model` field in `call_llm()` (e.g., `mixtral-8x7b-32768`, `gemma2-9b-it`)
- **Change system prompts** — Edit the `INTENT_SYSTEM` dict

## Tech Stack

- **Backend**: Python, FastAPI, mysql-connector-python
- **LLM**: Groq API (Llama 3 70B, free tier)
- **Frontend**: Vanilla HTML/CSS/JS (no build tools needed)
- **Database**: MySQL (your existing matrimony DB)

## License

MIT


