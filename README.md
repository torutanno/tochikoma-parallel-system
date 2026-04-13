# Tochikoma Parallel System

A multi-agent AI coordination framework built on [LangGraph](https://github.com/langchain-ai/langgraph). Five heterogeneous agents with distinct reasoning methodologies collaborate through a star topology with deliberate information asymmetry.

**This is not a swarm.** Each agent maintains a positioned perspective. Consensus is not the goal — dialectical synthesis is.

## Architecture

```
                    ┌─────────────┐
                    │  Master A   │
                    │ (Dialectics)│
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────┴─────┐ ┌───┴───┐ ┌─────┴─────┐
        │ Worker B  │ │Wrkr C │ │ Worker D  │
        │ Lateral   │ │ First │ │  User     │
        │ Thinking  │ │Princpl│ │ Centric   │
        └───────────┘ └───────┘ └───────────┘

        ┌───────────┐       ┌──────────────────┐
        │ Auditor E │       │ External Slots   │
        │ Fact Check│       │ Claude/Gemini/   │
        └───────────┘       │ Grok             │
                            └──────────────────┘
```

### Agents and Thinking Methods

| Agent | Role | Primary Method | Subsets |
|-------|------|---------------|---------|
| **Master A** | Commander / Synthesizer | Dialectics | Thesis-antithesis-synthesis, sublation, dynamic turn strategy (diverge, oppose, converge) |
| **Worker B** | Philosophy / Horizontal | Lateral Thinking | De Bono's provocations, random entry, concept fan, challenge assumptions |
| **Worker C** | Logic / Analysis | First Principles | Decomposition, Aristotelian foundationalism, data-driven falsification, reductio ad absurdum |
| **Worker D** | UI/UX / Creativity | User-Centric Design Thinking | Empathy mapping, "How Might We" framing, rapid prototyping mindset, constraint-driven creativity |
| **Auditor E** | Oversight / Fact-check | Methodical Skepticism | Logical consistency audit, ethical risk detection, infinite loop detection, Cartesian doubt |

### Reasoning Modes

Master A supports switchable reasoning modes via the `!mode` command:

- **`!mode:auto`** — Master A selects deductive or inductive reasoning based on query characteristics (default)
- **`!mode:deductive`** — Prioritizes top-down reasoning: principles to specific conclusions
- **`!mode:inductive`** — Prioritizes bottom-up reasoning: specific observations to general laws

### Dynamic Turn Strategy

Each deliberation cycle (max 3 turns) follows a structured progression:

1. **Turn 1 — Divergence**: Workers generate maximally diverse perspectives
2. **Turn 2 — Opposition**: Contradictions between Workers are sharpened
3. **Turn 3 — Convergence**: Dialectical synthesis into actionable conclusions

### Key Design Decisions

1. **Star Topology with Information Asymmetry** — Workers B/C/D cannot see each other's full reasoning. Only Master A holds the complete picture.

2. **`[UNRESOLVED]` as First-Class Output** — The system can explicitly declare cognitive limits rather than forcing false consensus. Master A must pass a self-verification checklist before concluding.

3. **External Intelligence Slots** — Routable to Claude, Gemini, or Grok via `[ASK_CLAUDE]`, `[ASK_GEMINI]`, `[ASK_GROK]` directives or `!call:xxx` commands. Slot loop prevention is enforced.

4. **Config-Driven Architecture** — All agent prompts, models, and schedules are externalized to YAML. No prompt strings in application code.

5. **Autonomous Lifecycle** — Sleep/wake cycle, scheduled triggers (morning briefing, noon disruption, night audit), and REM sleep memory consolidation at midnight.

## Project Structure

```
tochikoma_v5/
├── main.py                     # Entry point (Discord bot)
├── config/
│   ├── agents.yaml.example     # Agent and slot configuration template
│   └── schedules.yaml.example  # Schedule configuration template
├── domain/                     # Domain layer
│   ├── state.py                # LangGraph State schema
│   ├── routing.py              # Routing logic and directive detection
│   └── lifecycle.py            # Sleep/wake and autonomous triggers
├── application/                # Application layer
│   ├── nodes.py                # All LangGraph node functions
│   ├── graph_builder.py        # StateGraph construction
│   ├── config_loader.py        # YAML config loading and prompt rendering
│   ├── command_parser.py       # Discord command parsing
│   └── text_cleaner.py         # LLM output sanitization
├── infrastructure/             # Infrastructure layer
│   ├── llm_providers.py        # LLM instance factory
│   ├── discord_io.py           # Discord webhook integration
│   ├── vector_store.py         # ChromaDB vector store
│   ├── web_search.py           # Web search tool
│   └── scheduler.py            # APScheduler configuration
├── analysis/                   # Evaluation framework
│   ├── collector.py            # Session metrics collector
│   ├── metrics.py              # Embedding distance calculations
│   └── report_generator.py     # Evaluation report generation
└── requirements.txt
```

## Setup

### Prerequisites

- Python 3.10+
- Google Cloud project with Vertex AI API enabled
- Discord bot token and webhook URL
- (Optional) Anthropic API key, xAI API key

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/tochikoma-parallel-system.git
cd tochikoma-parallel-system

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your API keys

cp config/agents.yaml.example config/agents.yaml
# Customize agent models and prompts

cp config/schedules.yaml.example config/schedules.yaml
# Set your timezone and trigger schedule
```

### Run

```bash
python3 main.py
```

## Discord Commands

| Command | Description |
|---------|-------------|
| `!reset` | Clear short-term memory and slot bans |
| `!call:claude` | Force-invoke Claude slot |
| `!call:grok` | Force-invoke Grok slot |
| `!call:gemini` | Force-invoke Gemini slot |
| `!ban:claude` | Ban autonomous Claude invocation |
| `!unban:claude` | Lift Claude ban |
| `!mode:deductive` | Switch to deductive reasoning |
| `!mode:inductive` | Switch to inductive reasoning |
| `!mode:auto` | Return to automatic mode selection |
| `!eval` | Generate evaluation report |
| `!test:morning` | Manually trigger morning routine |
| `!test:rem` | Manually trigger REM sleep batch |

## Evaluation Framework

Per-session metrics with embedding distance calculations (Gemini Embedding 2):

- **Worker Dispersion**: Cosine distance between Worker B/C/D outputs
- **Convergence Rate**: Distance reduction across turns
- **External Intelligence Contribution**: Slot response impact on synthesis

Generate reports via `!eval` or find them in `reports/`.

## License

[FSL-1.1-MIT](LICENSE) — Functional Source License, Version 1.1, with MIT future license.

- **Now through 2028-04-13**: Free for personal, educational, research, and internal business use. Competing use restricted.
- **After 2028-04-13**: Full MIT License.

## Author

**Toru Tanno** — [L.S.D. (Laboratory of Scarlet Decadence)](https://losd57.substack.com)

A project exploring multi-agent coordination as cognitive architecture, not optimization pipeline.
