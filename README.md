# PressArchive

An AI research assistant built on top of Umar Cheema's 897-article journalism archive (2011–2026). The goal is to let Umar search his own prior reporting quickly, surface patterns across years of coverage, and get drafting help — all grounded in what he has actually documented, not in what a language model happens to believe.

This is the first working MVP of a broader anti-disinformation platform. It is not a finished product.

---

## What it does

PressArchive runs as a set of AI agents connected to Slack. You can ask it things like:

- *"What have I written about enforced disappearances?"*
- *"Is there a pattern in my ISI coverage?"*
- *"Help me structure a story about the Supreme Court's latest transparency ruling."*

It searches the archive and tells you what it found. It does not tell you whether claims are true or false. That distinction is intentional and matters — see [Limitations](#limitations).

---

## Architecture

```
Slack (Socket Mode)
       │
       ▼
  OpenClaw Gateway
  (local, port 18789)
       │
       ├── Agent: main         → workspace/main/
       ├── Agent: news-monitor → workspace/news-monitor/
       └── Agent: drafting     → workspace/drafting/
              │
              ▼
       archive-search skill
              │
              ▼
     archive_search.py
              │
       ┌──────┴──────┐
       ▼             ▼
  Chroma DB    Ollama (nomic-embed-text)
  (local,      (local embedding model,
  chroma_db/)   http://localhost:11434)
```

### Components

**OpenClaw** — the agent runtime. Manages agents, skills, Slack integration, and model routing. Config at `~/.openclaw/openclaw.json`. Each agent has a workspace directory containing its `AGENTS.md` (identity and behavioral rules), `USER.md`, and a `skills/` subfolder.

**Chroma DB** — local vector database at `./chroma_db`, collection `umar_archive`. Stores embeddings for 897 articles. Queried via cosine similarity against an embedded search phrase.

**Ollama** — runs locally, used for two things: generating embeddings at index time (via `nomic-embed-text`) and as a fallback inference model (`gemma4:latest`). Must be running before any search or indexing.

**OpenRouter** — hosted API routing to `anthropic/claude-haiku-4-5`, used as the primary inference model. Requires `OPENROUTER_API_KEY` in `~/.openclaw/.env`.

**Slack** — the user-facing interface. PressArchive connects via Socket Mode (no public endpoint needed). Credentials in `~/.openclaw/.env`.

---

## The three agents

All three agents have access to the `archive-search` skill. Their `AGENTS.md` files give them distinct identities and behavioral constraints.

### `main` (default)

The general-purpose journalist assistant. Use it for open-ended queries: finding past coverage, checking whether a claim has appeared in the archive before, or asking follow-up questions about what the reporting found. It is framed as a research assistant, not a fact-checker — it surfaces evidence, it does not issue verdicts.

Invoke via Slack (default agent) or: `openclaw agent --agent main --message "..."`

### `news-monitor`

Focused on pattern recognition across time. Given a topic, person, or institution, it searches the archive and returns a structured briefing: which articles exist, what they found, where coverage intensified or went quiet, and what gaps exist. Useful for "what's my prior work on X" before starting a new investigation.

Invoke: `openclaw agent --agent news-monitor --message "..."`

### `drafting`

Editorial collaborator. Helps with lead paragraphs, story structure, argument pressure-testing, and headline options. It will not invent facts — if it needs something it doesn't have, it leaves an explicit placeholder (`[VERIFY: source needed]`) rather than filling the gap with plausible-sounding detail. It asks for material before it writes.

Invoke: `openclaw agent --agent drafting --message "..."`

---

## The archive-search skill

Located at `~/.openclaw/workspace/skills/archive-search/SKILL.md` (and mirrored into each agent's `skills/` subfolder — OpenClaw resolves skills per-workspace, not globally).

The skill instructs the model to run `archive_search.py` via the `exec` tool:

```bash
"C:\Users\HP\anaconda3\envs\editorial_assistant\python.exe" \
  "C:\Users\HP\OneDrive\Desktop\OpenClaw\archive_search.py" \
  "QUERY TEXT HERE" \
  --top-k 5 \
  --persist "C:\Users\HP\OneDrive\Desktop\OpenClaw\chroma_db"
```

The script embeds the query via Ollama (`nomic-embed-text`), queries Chroma, and returns JSON with `headline`, `date`, `byline`, `excerpt`, and `distance` for each result. The skill instructs the model to report results by headline and date, paraphrase the substance, and say plainly if nothing was found.

---

## Two-model setup

| | Primary | Fallback |
|---|---|---|
| **Provider** | OpenRouter | Ollama (local) |
| **Model** | `anthropic/claude-haiku-4-5` | `gemma4:latest` |
| **Tool-calling** | Reliable | Works but slow and occasionally unreliable |
| **Speed** | Fast | Slow on CPU-only hardware |
| **Cost** | Per-token via OpenRouter | Free, runs locally |

The primary model is what runs in normal use. The fallback activates if OpenRouter is unreachable. `phi3:latest` is also installed locally but has no tool-calling capability and cannot invoke `archive-search` — do not use it for agent tasks.

This is a side-by-side comparison of hosted vs. local inference, one of the project's original design goals. In practice, the hosted model wins on every practical dimension on this hardware.

---

## Setup

### Prerequisites

- Node.js (for OpenClaw CLI)
- Python with `conda`, environment `editorial_assistant` (`chromadb`, `yt-dlp`)
- Ollama running locally with `nomic-embed-text` and `gemma4:latest` pulled
- OpenRouter API key
- Slack app with Socket Mode enabled (Bot Token + App Token)

### Install OpenClaw

```bash
npm install -g openclaw
```

### Configure credentials

Add to `~/.openclaw/.env`:

```
OPENROUTER_API_KEY=...
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
```

### Build the index

```bash
conda activate editorial_assistant
python build_index.py \
  articles_2011.json articles_2012.json articles_2013.json \
  articles_2014.json articles_2015on.json \
  --backend ollama \
  --persist ./chroma_db
```

This takes a while on first run. Ollama must be running.

### Start the gateway

```bash
openclaw gateway stop       # stop any existing instance or scheduled task
openclaw gateway run --force
```

The gateway must be restarted after any change to `openclaw.json` or skill files. Live reload is unreliable.

### Verify agents

```bash
openclaw skills check --agent main
openclaw skills check --agent news-monitor
openclaw skills check --agent drafting
```

Each should report `archive-search` as ready and visible to model. If it shows 0 visible, check that `skills/archive-search/SKILL.md` exists inside that agent's workspace directory.

### Test via CLI

```bash
openclaw agent --agent main --message "what have I written about judicial independence"
openclaw agent --agent news-monitor --message "what patterns do you see in my ISI coverage"
openclaw agent --agent drafting --message "help me write a lead for a story about X"
```

---

## File structure

```
OpenClaw/                          ← this repo / working directory
├── archive_search.py              ← Chroma query script (the core search tool)
├── build_index.py                 ← builds the Chroma index from article JSON
├── fetch_youtube_archive.py       ← pulls YouTube transcripts (resumable)
├── chroma_db/                     ← Chroma vector database (local, not in git)
├── articles_2011.json             ← parsed article data by year
├── articles_2012.json
├── articles_2013.json
├── articles_2014.json
├── articles_2015on.json
├── articles_vlog.json             ← YouTube transcripts (partial, see limitations)
└── articles_vlog_skipped.json     ← rate-limit failures (NOT genuine no-caption skips)

~/.openclaw/
├── openclaw.json                  ← main config (agents, models, channels)
├── .env                           ← secrets (not in git)
└── workspace/
    ├── skills/
    │   └── archive-search/
    │       └── SKILL.md
    ├── main/
    │   ├── AGENTS.md
    │   ├── USER.md
    │   └── skills/archive-search/SKILL.md
    ├── news-monitor/
    │   ├── AGENTS.md
    │   ├── USER.md
    │   └── skills/archive-search/SKILL.md
    └── drafting/
        ├── AGENTS.md
        ├── USER.md
        └── skills/archive-search/SKILL.md
```

---

## Limitations

### YouTube archive not indexed

Umar's YouTube channel (`@UmarCheemaExclusive`, 804 videos) has not been indexed. `fetch_youtube_archive.py` hit HTTP 429 rate limiting during the first fetch attempt. The script is resumable, but `articles_vlog_skipped.json` currently contains rate-limit failures, not genuine "no captions" results. Before retrying, that file must be cleared — otherwise the resume logic will treat those videos as permanently done and skip them.

### Verdict language

Language models have a strong tendency to issue flat verdicts ("This claim is TRUE / FALSE") even when instructed not to. The current approach works around this by framing the use case as evidence retrieval rather than fact-checking — the skill instructs the model to report what the archive says, not to adjudicate the claim. This is more honest about what the system can actually do. It does not fully solve the problem; with some models or prompts the verdict instinct resurfaces. Ongoing vigilance required.

### Local model limitations

`gemma4:latest` (fallback) is slow on CPU-only hardware and unreliable for tool-calling. `phi3:latest` has no tool-calling capability at all. The system degrades meaningfully without an OpenRouter connection.

### 897 of 902 articles indexed

Five articles from the print archive were not successfully indexed. Reason not investigated; likely parsing failures in the source JSON.

### Skill resolution is per-workspace

OpenClaw resolves skills from each agent's own workspace `skills/` folder. The `defaults.skills` allowlist in `openclaw.json` is necessary but not sufficient — the SKILL.md file must physically exist in each agent's workspace. Any new agent added to the config needs its own copy of the skill file.

### No live web search

The system only knows what is in the archive. It cannot search the web, check current news, or retrieve information published after the last index build. It will not tell you if it doesn't know something unless the archive explicitly comes up empty.
