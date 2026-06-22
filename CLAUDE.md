# TruthLedger / OpenClaw Project — Context for Claude Code

## What this is
Umar Cheema (veteran Pakistani investigative journalist) is building an
OpenClaw-based AI assistant on top of his 897-article journalism archive
(2011-2026). This started as a bootcamp assignment (multi-agent system,
Slack channel, model comparison, full demo) but is also the real first MVP
of his broader "TruthLedger" anti-disinformation platform. The assignment
deadline has already passed; the goal now is a genuinely working, honest
build, not just a checkbox submission.

## What's already working (do not need to be rebuilt)
- Slack channel ("TruthLedger" app, "Truth Tracker" workspace) connected via
  OpenClaw's Socket Mode, fully working end to end.
- 897 of 902 articles indexed into a Chroma vector DB at
  `C:\Users\HP\OneDrive\Desktop\OpenClaw\chroma_db` (collection
  `umar_archive`), embedded via Ollama's `nomic-embed-text` model.
- `archive_search.py` in the same folder: a working script that embeds a
  query and searches that Chroma DB, returns JSON results. Proven reliable.
- A working OpenClaw skill `archive-search`, located at
  `C:\Users\HP\.openclaw\workspace\skills\archive-search\SKILL.md`, which
  wraps `archive_search.py` via the `exec` tool. This skill handles both
  general search ("what have I written about X") and claim verification
  framed as evidence-retrieval (not verdict-issuing), see that file for the
  exact rules already encoded in it.
- Two configured models: `openrouter/anthropic/claude-haiku-4-5` (primary,
  fast, reliable tool-calling) and `ollama/gemma4:latest` (local fallback,
  works but slow on this CPU-only Windows machine, and historically
  unreliable specifically for tool-calling). `ollama/phi3:latest` also
  exists locally but lacks tool-calling capability entirely, do not use it
  for anything that needs the archive-search skill.
- Main config file: `C:\Users\HP\.openclaw\openclaw.json`. Global secrets:
  `C:\Users\HP\.openclaw\.env` (Slack tokens, OpenRouter key, Ollama
  marker). The gateway must be restarted (`openclaw gateway stop` then
  `openclaw gateway run --force`) after any config or skill file change to
  reliably pick it up, live reload has proven unreliable.

## What's NOT working / not yet done
- True per-agent differentiation. As of last session, `agents.list` entries
  in openclaw.json do NOT support a custom instructions/system-prompt field
  directly, only shared workspace files (AGENTS.md) or skills shape agent
  behavior. Three agent entries exist (`main`, `news-monitor`, `drafting`)
  but they are currently functionally identical, same skill, same shared
  workspace. Three AGENTS.md drafts exist (provided separately:
  AGENTS_main.md, AGENTS_news_monitor.md, AGENTS_drafting.md) and need to be
  placed into separate per-agent workspace folders so each agent actually
  behaves differently. This is the main remaining task.
- The YouTube vlog archive (804 videos, channel
  https://www.youtube.com/@UmarCheemaExclusive) is NOT yet indexed. The
  fetch script (`fetch_youtube_archive.py`, same folder) has repeatedly hit
  YouTube's HTTP 429 rate limiting on this network. It is resumable
  (skips already-completed video IDs on rerun) but the `articles_vlog_skipped.json`
  file needs to be cleared before any retry, since it currently contains
  rate-limit failures, not genuine "no captions" results, and the resume
  logic would otherwise treat those as permanently done.
- A standalone `verification` agent (separate from `main`) was attempted
  and abandoned: `openclaw skills check --agent verification` showed
  0 skills visible to it, likely because it lacked an explicit `workspace`
  field and defaulted to its own empty one. Not currently in the config.

## Known gotchas from past sessions (avoid repeating these)
- Windows PATH for Node/npm was broken and is now fixed at the system
  level (`C:\Program Files\nodejs\` and
  `C:\Users\HP\AppData\Roaming\npm\` added to permanent User PATH).
  Python/conda is separate: the `editorial_assistant` conda environment
  must be activated (`conda activate editorial_assistant`) for any Python
  script, but NOT for `openclaw` commands themselves.
- A Windows Scheduled Task ("OpenClaw Gateway") sometimes runs in the
  background and conflicts with a manually-started foreground gateway.
  Always run `openclaw gateway stop` before `openclaw gateway run --force`.
- Skill files (SKILL.md) appear to be loaded once at gateway startup, not
  live-reloaded, always restart the gateway after editing one.
- The model previously produced flat verdicts ("CLAIM IS TRUE") and mixed
  in ungrounded outside-knowledge facts despite explicit instructions not
  to, even with a guaranteed-fresh session. This was worked around by
  reframing the use case as retrieval/search rather than adjudication
  rather than continuing to fight it with stronger prompt wording, see the
  archive-search SKILL.md for the current approach.

## Goals for this session
1. Give the three agents (main, news-monitor, drafting) real distinct
   behavior using separate workspaces and the AGENTS.md files already
   drafted, then verify each with `openclaw skills check --agent <id>`.
2. Retest all three through both the CLI (`openclaw agent --agent <id>
   --message "..."`) and Slack to confirm real behavioral differences.
3. If time allows, retry the YouTube fetch (clear the skipped file first)
   and re-run `build_index.py` to extend the archive with vlog transcripts.
4. Flag anything broken honestly rather than working around it silently,
   this project's whole design philosophy is "show evidence, don't oversell
   capability," and that should apply to how its own development is
   reported too.
