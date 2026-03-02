# 🧠 StudyPartner AI

> **AI study tutor that watches your screen and coaches you in real-time using research-backed techniques.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Powered by Gemini](https://img.shields.io/badge/Powered%20by-Gemini%202.0%20Flash-orange.svg)](https://ai.google.dev/)

---

## What It Does

StudyPartner AI is a **real-time, voice-enabled study tutor** that:

1. **📸 Observes** your screen via periodic screenshots (privacy-filtered)
2. **🧠 Understands** what you're studying and what phase you're in
3. **🗣️ Coaches** you using science-backed study techniques (brain dumps, Feynman, interleaving, spaced repetition)
4. **🧬 Learns** what works for *you* and adapts its coaching strategy over time
5. **🔒 Keeps your data yours** — all personal data stays on your Mac, cloud is stateless

### How It Works

```
Your Screen → Screenshot → Privacy Gate → Cloud Run → Gemini 2.0 Flash → Coaching Nudge
                                     (encrypted)    (stateless)         (voice or notification)
                                                                              ↓
                                                              Adaptive Engine learns from your response
```

**Your Mac is the memory. Google Cloud is the transient brain.**
The brain processes and forgets. The memory persists, learns, and evolves.

---

## Quick Start

### Prerequisites

- macOS 13+ (Ventura or later)
- Python 3.11+
- A [Google Cloud](https://cloud.google.com/) account
- A [Gemini API key](https://aistudio.google.com/apikey)
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed

### Install

```bash
pip install studypartner-ai
```

### Deploy Your Backend

```bash
# Set your API key and project
export GEMINI_API_KEY="your-key-here"
export GCP_PROJECT_ID="your-project-id"

# One-command deploy to Cloud Run
studypartner deploy
```

### Configure

```bash
studypartner setup        # Interactive wizard — enters backend URL, sets preferences
```

### Start Studying

```bash
studypartner start                          # Auto-detect topic from screen
studypartner start --topic "Bash Scripting" # Start with a specific topic
```

---

## Features

### 📸 Smart Screen Analysis
Gemini 2.0 Flash natively reads your screen and understands what you're doing — coding, reading docs, browsing, or using AI chat.

### 🗣️ Voice Coaching (Gemini Live API)
Real-time voice conversation with your tutor. Ask questions, get quizzed, and discuss concepts naturally.

### 🧬 Self-Improving (Adaptive Engine)
The system learns from your behavior:
- Which coaching techniques work for you
- Your optimal session length
- When you're most focused
- How you prefer to receive nudges

Every session makes the next one better.

### 🔒 Privacy-First Architecture
- Screenshots pass through a **Privacy Gate** (blurs banking apps, redacts PII)
- Cloud Run backend is **stateless** — zero data retention
- All personal data (sessions, profiles, coaching history) **stays on your Mac**
- `studypartner reset --all` wipes everything with one command

### 🖥️ OS-Native Integration
- Lives in your **menu bar** — no Dock icon, no windows
- Activates with **Focus Mode**
- Delivers coaching via **native macOS notifications**
- Feels built into macOS, not a third-party app

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│  YOUR MAC (Data Owner + Adaptive Engine)          │
│                                                    │
│  Screenshot → Privacy Gate → Context Composer     │
│       ↓                           ↓                │
│  Save locally      Build context packet            │
│                    (history + adaptive weights)     │
│                           ↓                        │
│                    Send to Cloud Run ─────────────┼──→ Google Cloud Run
│                           ↓                        │    (stateless)
│                    Receive coaching ←─────────────┼──← Gemini 2.0 Flash
│                           ↓                        │
│  Deliver nudge ← Adaptive Engine learns from       │
│  (voice/notification)    user response             │
│                                                    │
│  SQLite DB │ Learning Profile │ Adaptive Profile   │
└──────────────────────────────────────────────────┘
```

See [architecture.md](architecture.md) for the full technical architecture.

---

## CLI Reference

| Command | Description |
|---|---|
| `studypartner start` | Start a study session |
| `studypartner start --topic "X"` | Start with a specific topic |
| `studypartner stop` | End the current session |
| `studypartner status` | Show session status |
| `studypartner setup` | First-run setup wizard |
| `studypartner deploy` | Deploy backend to Cloud Run |
| `studypartner history` | View past sessions |
| `studypartner review` | Show topics due for spaced review |
| `studypartner reset --yes` | Wipe all local data |

---

## The Science Behind It

StudyPartner applies techniques from cognitive science research:

| Technique | How StudyPartner Uses It |
|---|---|
| **Spaced Practice** | Tracks topics, schedules reviews on the forgetting curve |
| **Retrieval Practice** | Prompts brain dumps at optimal intervals |
| **Feynman Technique** | Voice coaching: "Explain this concept to me simply" |
| **Interleaving** | Detects blocked practice, suggests topic switching |
| **Worked Examples** | Detects new topics, suggests studying examples first |
| **Cognitive Load Protection** | Adaptive Pomodoro timing + enforced breaks |
| **AI as Tutor, Not Crutch** | Detects AI copy-paste patterns, warns user |

See [study_guide.md](study_guide.md) for the full Permanent Learning Playbook.

---

## Development

### Setup for Development

```bash
git clone https://github.com/YOUR_USERNAME/studypartner-ai.git
cd studypartner-ai
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest tests/
```

### Run Linter

```bash
ruff check src/
```

### Run Server Locally

```bash
GEMINI_API_KEY="your-key" uvicorn studypartner.server.main:app --reload --port 8080
```

---

## Tech Stack

| Component | Technology |
|---|---|
| **Client** | Python 3.11 + pyobjc |
| **Screen Capture** | macOS Quartz (CoreGraphics) |
| **Notifications** | macOS NSUserNotification |
| **Database** | SQLite |
| **Backend** | FastAPI on Google Cloud Run |
| **AI Model** | Gemini 2.0 Flash |
| **Agent Framework** | Google ADK |
| **CLI** | Typer + Rich |

---

## License

MIT — see [LICENSE](LICENSE).

---

## Hackathon

Built for the **Gemini Live Agent Challenge** — a real-time, vision-enabled, voice-capable AI study tutor.

Category: **🗣️ Live Agents**

`#GeminiLiveAgentChallenge`
