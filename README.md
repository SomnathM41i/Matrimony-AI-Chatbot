# Emperor Nexus Authority (E.N.A.) — Matrimony AI Chatbot

An intelligent AI assistant by **Emperor Nexus Authority (E.N.A.)** that connects to your MySQL matrimony database and answers user questions using Groq's free LLM (Llama 3).

## How It Works

```
User question → Backend API → Intent detection → SQL query → MySQL Database → LLM → Natural reply
```

The chatbot:
1. Detects what the user is asking (pricing, profiles, support, etc.)
2. Queries your live MySQL database for relevant data
3. Sends the data to Groq's Llama 3 70B (free) for a natural language response

## Features

- **AI Chat Interface** — Modern React frontend with real-time messaging
- **User Authentication** — JWT-based login/register system
- **Conversation History** — Browse, search, and resume past conversations
- **Membership Plans** — Query `membershipplan` table for pricing, duration, features
- **Profile Search** — Search `register` table by gender, age, city, religion, caste, marital status
- **FAQs** — Answers from CMS help pages
- **Success Stories** — Share testimonials (from `successstory` / `testimonial` tables)
- **Support** — Contact details from `siteconfig` and CMS
- **Layered Architecture** — Routes → Services → Repositories → Models (myvivahai-inspired)

## Prerequisites

- Python 3.10+
- Node.js 18+
- MySQL database (remote or local)
- Free Groq API key from https://console.groq.com

## Quick Start

### 1. Backend Setup

```bash
cd backend
cp .env.example .env          # Fill in: GROQ_API_KEY, DB credentials
python -m venv venv
venv\Scripts\activate         # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup (in another terminal)

```bash
cd frontend
npm install
npm run dev
```

**App:** http://localhost:5173 · **API Docs:** http://localhost:8000/docs

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GROQ_API_KEY` | — | Groq API key (https://console.groq.com) |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | LLM model |
| `DB_HOST` | `localhost` | MySQL host |
| `DB_PORT` | `3306` | MySQL port |
| `DB_USER` | `root` | MySQL user |
| `DB_PASSWORD` | — | MySQL password |
| `DB_NAME` | `matrimony` | MySQL database |
| `SECRET_KEY` | `change-me` | JWT signing key |
| `DATABASE_URL` | `sqlite+aiosqlite:///./storage/chatbot.db` | Local auth DB (SQLite) |

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Frontend (React 18 + Vite)          │
│  ┌─────────┐ ┌────────────┐ ┌───────────────┐  │
│  │ Zustand │ │ React Query│ │ React Router  │  │
│  │ (Auth)  │ │ (Server    │ │ (6.23)        │  │
│  │         │ │  State)    │ │               │  │
│  └─────────┘ └─────┬──────┘ └───────┬───────┘  │
│                    │                │           │
│  ┌─────────────────┴────────────────┴────────┐ │
│  │           Pages / Components              │ │
│  │  Login | Chat | History | Sidebar        │ │
│  └─────────────────┬─────────────────────────┘ │
│                    │ HTTP (JWT Bearer Token)    │
└────────────────────┼────────────────────────────┘
                     │
┌────────────────────┼────────────────────────────┐
│          FastAPI Backend (localhost:8000)        │
│  ┌─────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │  Auth   │ │  Chat    │ │  Admin Routes    │ │
│  │ Routes  │ │  Routes  │ │  (health, stats) │ │
│  └────┬────┘ └────┬─────┘ └────────┬─────────┘ │
│       │           │                │           │
│  ┌────┴───────────┴────────────────┴────────┐ │
│  │            Services Layer                │ │
│  │  AuthService | ChatService | LLMService  │ │
│  │  DBQueryService                          │ │
│  └────┬───────────┬────────────────┬────────┘ │
│       │           │                │           │
│  ┌────┴────┐ ┌───┴────┐ ┌─────────┴────────┐ │
│  │   AI    │ │ Repos  │ │  MySQL Connector │ │
│  │  Layer  │ │ (DAL)  │ │  (matrimony DB)  │ │
│  │ LLM     │ │ User   │ │                  │ │
│  │ Intent  │ │ Conv   │ │  + SQLite        │ │
│  │ SQL Gen │ │ Msg    │ │  (auth DB)       │ │
│  └─────────┘ └────────┘ └──────────────────┘ │
└─────────────────────────────────────────────────┘
```

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Pydantic Settings
│   │   ├── database.py          # SQLAlchemy async engine
│   │   ├── api/                 # Route handlers
│   │   │   ├── auth_routes.py   # Login/Register/Me
│   │   │   ├── chat_routes.py   # Message processing
│   │   │   ├── history_routes.py# Conversation CRUD
│   │   │   └── admin_routes.py  # Health/Stats
│   │   ├── core/                # Auth, security, constants
│   │   ├── models/              # SQLAlchemy models
│   │   ├── repositories/        # Data access layer
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── services/            # Business logic
│   │   └── ai/                  # LLM, intent, SQL gen
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── main.jsx             # App bootstrap
│   │   ├── App.jsx              # Router provider
│   │   ├── app/                 # Router, Zustand store
│   │   ├── components/ui/       # ChatMessage, Sidebar, etc.
│   │   ├── hooks/               # useAuth, useChat, useHistory
│   │   ├── layouts/             # AuthLayout, ChatLayout
│   │   ├── pages/               # Login, Chat, History
│   │   ├── services/            # Axios API client
│   │   └── styles/              # Tailwind globals
│   ├── package.json
│   └── vite.config.js
├── docker-compose.yml
└── .gitignore
```

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/` | GET | No | Server status |
| `/health` | GET | No | Health check |
| `/api/auth/login` | POST | No | User login |
| `/api/auth/register` | POST | No | User registration |
| `/api/auth/me` | GET | Yes | Current user |
| `/api/chat` | POST | Yes | Send message |
| `/api/conversations` | GET | Yes | List conversations |
| `/api/conversations/{id}` | GET | Yes | Get conversation |
| `/api/conversations/{id}` | PATCH | Yes | Rename conversation |
| `/api/conversations/{id}` | DELETE | Yes | Delete conversation |
| `/api/admin/stats` | GET | Yes | Database statistics |

## Tech Stack

| Layer | Tech |
|-------|------|
| **Frontend** | React 18 + Vite + Tailwind CSS + Framer Motion |
| **Backend** | FastAPI (async) + SQLAlchemy 2.0 |
| **AI** | Groq API (Llama 3.3 70B) |
| **Auth** | JWT (access + refresh tokens) |
| **Databases** | SQLite (auth/auth) + MySQL (matrimony data) |
| **State** | Zustand (client) + TanStack React Query (server) |

## License

MIT
