# Project Astra: Sovereign AI Influencer Agent

**Version:** 2026.6.0  
**Status:** Approved for Heuristic Headless Deployment  
**Runtime:** GitHub Actions / Ubuntu-22.04 / Python 3.11

---

## Overview

Project Astra is a 100% autonomous, zero-CapEx digital persona system that generates photorealistic images of "Astra" via Gemini's web interface and posts them to social media schedulers (Buffer/Metricool) using a 5-Layer Stealth Stack.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PROJECT ASTRA v2026.6.0                   │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Network Obfuscation    → Cloudflare WARP CLI      │
│  Layer 2: Stealth Plugins        → webdriver, WebGL mocks   │
│  Layer 3: Rebrowser Playwright   → CDP leak patches         │
│  Layer 4: Biometric Simulation   → Bezier curves, typing    │
│  Layer 5: Cookie Authentication  → Session restoration      │
├─────────────────────────────────────────────────────────────┤
│  Engine:     AI Chrome Heuristic Navigator (GLM-4.7)        │
│  Generators: Prompt Synthesizer, Caption Generator          │
│  Platforms:  Buffer, Metricool, Social Champ                │
│  Utils:      State Manager, Telemetry, Logger               │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- GitHub repository with secrets configured
- Discord webhook URL (for alerts)

### Installation

```bash
# Clone and setup
git clone <repo-url>
cd project-astra
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Set environment variables
export GLM_API_KEY="your-glm-api-key"
export GEMINI_COOKIES='[...]'       # JSON array of cookies
export SCHEDULER_COOKIES='[...]'    # JSON array of cookies
export DISCORD_WEBHOOK="https://discord.com/api/webhooks/..."
```

### Run Locally

```bash
# Full orchestrator run
python -m src

# With headed browser for debugging
HEADED=true python -m src

# Skip WARP (for local dev)
SKIP_WARP=true python -m src
```

### Run Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# E2E tests (requires Playwright)
pytest tests/e2e/ -v

# All tests
pytest -v
```

## GitHub Secrets Required

| Secret | Description |
|--------|-------------|
| `GEMINI_COOKIES` | JSON array of authenticated Gemini session cookies |
| `SCHEDULER_COOKIES` | JSON array of Buffer/Metricool session cookies |
| `GLM_API_KEY` | API key for GLM-4.7 heuristic reasoning |
| `DISCORD_WEBHOOK` | Discord webhook URL for telemetry alerts |

## State Machine

```
IDLE → INITIALIZING → GENERATING_MEDIA → VALIDATING → GENERATING_CAPTION → POSTING → LOGGING → FINISHING
```

- **Circuit Breaker:** 3 consecutive failures → agent goes dark + alert
- **Scheduling Gates:** Only runs during Morning (08:30-10:00 IST) and Evening (20:30-22:00 IST) windows
- **Daily Limit:** Max 2 posts per day

## Project Structure

```
├── src/
│   ├── orchestrator.py           # Main state machine
│   ├── constants.py              # Base DNA, scenes, selectors
│   ├── engine/                   # AI Chrome modules
│   │   ├── heuristic_navigator.py
│   │   ├── dom_sanitizer.py
│   │   ├── vision_fallback.py
│   │   └── interaction_handler.py
│   ├── generators/               # Content generation
│   │   ├── prompt_synthesizer.py
│   │   ├── gemini_client.py
│   │   ├── caption_generator.py
│   │   └── media_validator.py
│   ├── platforms/                # Scheduler automation
│   │   ├── buffer.py
│   │   ├── metricool.py
│   │   └── social_champ.py
│   └── utils/                    # Infrastructure
│       ├── stealth_manager.py
│       ├── biometric_sim.py
│       ├── warp_manager.py
│       ├── state_manager.py
│       ├── telemetry.py
│       └── logger.py
├── tests/
│   ├── unit/                     # Logic tests
│   ├── integration/              # GLM/Playwright bridge
│   ├── e2e/                      # Full pipeline smoke tests
│   └── fixtures/                 # Mock HTML and cookies
├── .github/workflows/
│   ├── production_cron.yml       # Main scheduler
│   ├── ci_cd_tests.yml           # Test runner
│   ├── manual_trigger.yml        # Debug trigger
│   └── cookie_rotation.yml       # Cookie health check
└── data/state_log.json           # Execution state
```

## Configuration

Key parameters in `src/constants.py`:

- `BASE_DNA_STRING`: Physical persona description (must be in every prompt)
- `MORNING_SCENES` / `EVENING_SCENES`: Contextual modifiers
- `POSTING_WINDOWS`: IST schedule constraints
- `MAX_DAILY_POSTS`: Daily volume cap
- `CONFIDENCE_THRESHOLD`: GLM-4.7 minimum confidence (80%)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| WARP not connecting | Check `warp=on` in trace; may need runner restart |
| Cookie expired | Refresh cookies from local browser; webhook will alert |
| GLM API errors | Check rate limits; implement exponential backoff |
| Image validation fails | Increase `MAX_GENERATION_RETRIES`; check Gemini output |
| Element not found | GLM may need re-prompt; check fallback selectors |

## License

Proprietary - See [LICENSE](LICENSE)

## Roadmap

- **Phase 1:** Static image generation + autonomous posting (Current)
- **Phase 2:** Video integration (Veo pipeline)
- **Phase 3:** RAG-based conversational LLM for DMs
- **Phase 4:** Dedicated VPS migration ($100/mo threshold)
- **Phase 5:** Custom LoRA model training ($2000/mo threshold)
