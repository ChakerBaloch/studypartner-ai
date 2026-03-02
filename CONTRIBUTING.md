# Contributing to StudyPartner AI

Thank you for your interest in contributing! 🧠

## Development Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/studypartner-ai.git
cd studypartner-ai

# Create virtualenv (Python 3.11+ required)
python3.12 -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Verify
studypartner --help
pytest tests/ -v
```

## Project Structure

```
src/studypartner/
├── cli.py                  # CLI commands (typer)
├── setup_wizard.py         # First-run setup
├── client/                 # Runs on user's Mac
│   ├── capture.py          # Screenshot engine
│   ├── preprocessor.py     # Privacy Gate
│   ├── context.py          # Context Composer
│   ├── session.py          # Main capture → analyze → nudge loop
│   ├── adaptive.py         # Self-improving engine
│   ├── database.py         # SQLite operations
│   ├── scheduler.py        # Spaced repetition (SM-2)
│   └── ...
├── server/                 # Runs on Cloud Run (stateless)
│   ├── main.py             # FastAPI endpoints
│   ├── agent.py            # Gemini integration
│   └── live_session.py     # Gemini Live API streaming
├── os_integration/         # macOS-specific integrations
│   ├── menu_bar.py         # NSStatusItem
│   ├── focus_mode.py       # Focus Mode detection
│   └── ...
└── shared/                 # Types shared between client/server
    ├── models.py           # Pydantic models
    ├── constants.py        # Paths, thresholds
    └── study_guide.py      # Study technique rules engine
```

## Running Tests

```bash
pytest tests/ -v            # Run all tests
pytest tests/test_adaptive.py  # Run specific test file
ruff check src/ tests/      # Lint
```

## Code Style

- **Formatter:** ruff (PEP 8 + line length 100)
- **Type hints:** required on all function signatures
- **Docstrings:** Google style, required on public functions
- **Privacy:** Never store anything on the server. Zero retention.

## Adding a New Study Technique

1. Add the technique to `src/studypartner/shared/study_guide.py` → `suggest_technique()`
2. Add it to `AdaptiveWeights.preferred_techniques` default dict in `models.py`
3. Update the system prompt in `server/agent.py`
4. Add a test in `tests/test_study_guide.py`

## Pull Request Process

1. Fork → branch → implement → test → PR
2. All tests must pass
3. No hardcoded secrets
4. Follow the privacy contract: nothing leaves the Mac except transient, encrypted data

## Environment Variables

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
# Fill in GEMINI_API_KEY and GCP_PROJECT_ID
```

## License

MIT — [LICENSE](LICENSE)
