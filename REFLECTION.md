# Project Reflection — PressArchive / TruthLedger

**Course:** Multi-Agent AI Systems
**Submitted by:** Umar Cheema
**Date:** June 2026

---

## What was built and why

The assignment required building a multi-agent AI system with at least two models, a communication channel, and distinct agent roles. I built something I actually needed rather than a toy: an AI research assistant on top of my own 897-article journalism archive spanning 2011 to 2026.

The practical problem: I have fifteen years of investigative reporting — on Pakistan's security sector, judiciary, corruption, and civil liberties — spread across files I cannot easily search by meaning. When starting a new story or verifying a claim, I want to know whether I have reported on this before, what I found, and when. A keyword search over filenames does not do this well. A vector search over embedded article content does.

The system — built on the OpenClaw agent runtime — connects to Slack and runs three agents: a general-purpose research assistant (`main`), a pattern-recognition agent for tracking topics across time (`news-monitor`), and an editorial collaborator for drafting (`drafting`). All three can query the archive via a custom skill that calls a Python search script against a local Chroma vector database.

This was simultaneously a bootcamp assignment and the first working version of a real tool I intend to use.

---

## Key technical decisions

**OpenClaw as the agent runtime.** The framework handles model routing, Slack integration via Socket Mode, workspace management, and skill loading. This avoided building agent infrastructure from scratch, which was not the point of the assignment. The tradeoff is that OpenClaw's documentation is sparse and its behaviour in edge cases had to be discovered empirically.

**Local vector database (Chroma) with local embeddings (Ollama / nomic-embed-text).** All article data stays on my machine. For journalism — where source confidentiality and unpublished research are real concerns — this matters. An external embedding API would have been faster to set up but would have sent article content to a third party.

**Two-model architecture.** The primary inference model is `anthropic/claude-haiku-4-5` via OpenRouter (hosted, fast, reliable tool-calling). The fallback is `gemma4:latest` running locally via Ollama (free, slower, less reliable for tool use on CPU-only hardware). This satisfied the assignment's model comparison requirement and reflects a real design tradeoff: the hosted model is strictly better in practice on this machine, but the local model preserves independence from external services.

**Evidence retrieval framing, not fact-checking.** After early testing showed the model producing flat verdicts ("This claim is TRUE") regardless of prompt instructions, the system was redesigned to frame all queries as evidence retrieval rather than claim adjudication. The skill instructs the model to report what the archive documents, not to rule on truth. This is both more honest about what the system can actually do and more useful journalistically — a journalist needs sources and evidence, not a verdict from an AI.

**Separate workspaces per agent.** Each agent was given its own workspace directory containing its identity file (`AGENTS.md`) and skill files. This is the mechanism OpenClaw uses for per-agent behavioural differentiation.

---

## What worked well

**The archive search pipeline.** `archive_search.py` → Chroma → Ollama embeddings is reliable and fast enough for practical use. Results are meaningfully relevant — not just keyword matches — and the JSON output is clean and easy for the model to parse. This part of the system required the least debugging.

**Slack integration.** Once the Socket Mode credentials were configured correctly, the gateway connected without issues and has remained stable. This is the right interface for a tool I want to use during actual reporting — it is already open and fits into a working journalist's day better than a web UI or CLI.

**Behavioral differentiation between agents.** After the workspace and skill issues were resolved, the three agents respond distinctly to the same underlying question. The news-monitor produces structured briefings with timelines and gap analysis; the drafting agent asks for material before it writes and refuses to invent detail; the main agent gives fluent research summaries. The `AGENTS.md` approach works, provided the file is actually loaded.

**The evidence-retrieval reframe.** Stepping back from the fact-checking framing and redesigning around evidence retrieval made the system more honest and more useful at the same time. This is a lesson about fitting tool design to actual capability rather than fighting a model's tendencies with increasingly aggressive prompt instructions.

---

## What did not work

### 1. The `agents.list` schema mistake

The assignment required multiple distinct agents. The initial assumption was that agent entries in `openclaw.json` could carry a custom system prompt or instructions field directly in the `agents.list` object. They cannot. OpenClaw's per-agent behavioural differentiation works through workspace files (`AGENTS.md`), not through inline config fields. Multiple agent entries existed in the config for weeks before it was understood that they were functionally identical because they all pointed to the same default workspace.

The time spent trying to differentiate agents through config fields that did not exist for that purpose was wasted. Reading the framework documentation more carefully at the start — or running a quick test to confirm the assumption — would have caught this immediately.

### 2. Verdict-language prompt compliance failure

Early versions of the system included explicit instructions in the skill file not to issue verdicts: "do not say 'this claim is true or false'", "frame responses as evidence summaries", and similar. The model ignored these instructions reliably. In testing across multiple sessions, with fresh context each time, the model continued producing flat verdict language.

This is a known behaviour of instruction-tuned language models: they have strong priors toward decisive-sounding outputs, and those priors can override explicit instructions in system prompts, especially when the prompt is long and the conflicting instruction is buried. The resolution — reframing the entire use case as retrieval rather than adjudication — addressed the symptom correctly but did not solve the underlying problem. If the prompting had been more carefully designed from the beginning (shorter, more specific, behaviorally tested), the workaround might not have been necessary.

The lesson is not just about prompt engineering. It is about not assigning tasks to models that exceed what their architecture reliably supports. A vector search returns evidence; adjudicating truth from evidence requires editorial judgment. Those are different things. The system now does the former and correctly leaves the latter to the journalist.

### 3. YouTube archive rate-limiting

Umar's YouTube channel (`@UmarCheemaExclusive`) contains 804 videos — a substantial body of broadcast journalism that would meaningfully extend the archive. `fetch_youtube_archive.py` was written to pull transcripts via `yt-dlp`, which requires no API key and works against public data. In testing, YouTube returned HTTP 429 (rate limiting) consistently before even a fraction of the archive was fetched.

The script was written to be resumable: it logs skipped videos to `articles_vlog_skipped.json` and skips them on rerun. The problem is that the skipped file now contains rate-limit failures, not genuine "no captions" cases. If the script is rerun without clearing that file, those videos will be permanently skipped.

This was not caught before it happened because the resume logic was not tested against a failure scenario — only against a successful partial run. The YouTube archive remains unindexed. The fix (clear the skipped file, retry with longer delays between requests) is straightforward but was not attempted again due to time constraints.

### 4. Per-workspace skill discovery

OpenClaw's documentation does not clearly state how skills are resolved for agents with custom workspace paths. The reasonable assumption was that `defaults.skills: ["archive-search"]` in the config would make the skill available to all agents regardless of their workspace. It does not — or at least, it is not sufficient.

OpenClaw resolves skills from the `skills/` subfolder of each agent's own workspace directory. The archive-search skill file (`SKILL.md`) existed only in the default workspace's skills folder. Agents with their own workspace paths could not find it. This was discovered through testing, not documentation: the `news-monitor` and `drafting` agents had zero skills visible and fell back to asking the user where the archive was stored.

The fix was to copy the `SKILL.md` into each agent workspace's `skills/` folder. This works, but it introduces a maintenance problem: any edit to the skill file must be made in multiple places. A better long-term approach would be a single shared skill file with agents referencing it by path, if the framework supports that.

The deeper problem is that the agent differentiation work — the part of the project meant to demonstrate multi-agent architecture — was delayed and nearly blocked by this infrastructure issue. It was not discovered until late because the main agent (which worked due to an existing SQLite cache from prior sessions) gave a false signal that the architecture was correct.

---

## Lessons learned

**Test assumptions about framework behaviour immediately.** Two of the four failures above (agents.list schema, skill resolution) were based on incorrect assumptions about how OpenClaw works. Both could have been caught in the first hour with a simple test. Instead, architecture decisions were built on top of them.

**Build the simplest thing first and verify it end to end.** The pipeline (archive → embeddings → Chroma → search → model → Slack) was the right thing to prove first. It worked, and having a working end-to-end path made everything else easier to reason about. The multi-agent layer should have been added after that foundation was solid, not in parallel.

**Prompt compliance is not guaranteed; design around it.** Detailed prompt instructions are not contracts. Models have strong behavioural priors that compete with instructions, especially in long prompts. The correct response to this is to redesign the task so the model is doing what it is good at, not to add more instructions.

**Resume logic needs to be tested against failure cases.** The YouTube skip file was designed for one failure mode (no captions) but encountered a different one (rate limiting). Resumable scripts should be tested by simulating the failure conditions they are meant to handle.

**"Working" and "working correctly" are different.** The main agent appeared to work with archive-search before the workspace issue was properly diagnosed. It was actually drawing on cached state from prior sessions. This masked a real bug for longer than it should have.

---

## What would be done differently, or next

**Different:** Start with a working single-agent prototype that covers the full stack, test it thoroughly, then add agents. Do not configure multiple agents before the first one is proven.

**Different:** Read the framework's workspace and skill resolution behaviour explicitly before designing around it, rather than inferring it from the config structure.

**Different:** Design prompt compliance tests (specific inputs, expected output patterns, pass/fail criteria) before writing production prompt instructions. Run them. If the model fails consistently, change the task framing rather than the instructions.

**Next:** Retry the YouTube fetch with rate-limit handling — exponential backoff, smaller batches, potentially over several days. Clear `articles_vlog_skipped.json` first. Re-run `build_index.py` once transcripts are retrieved. This would roughly double the archive's coverage of Umar's journalism output.

**Next:** Consolidate the archive-search skill into a single shared location and add a config-level path reference, rather than maintaining copies in each agent workspace. This is a maintenance burden as the skill evolves.

**Next:** Add a simple evaluation set — ten queries with known relevant articles — and run it against both models to generate concrete comparison numbers. The assignment required a model comparison, but the current comparison is qualitative ("hosted model is faster and more reliable"). Quantitative accuracy and latency data would make it more rigorous.

**Longer term:** The evidence-retrieval framing is correct as a design philosophy, but the system currently only surfaces archive evidence. A genuinely useful anti-disinformation tool would also surface what is *absent* from the archive — claims for which there is no prior reporting — and flag that absence explicitly rather than returning empty results silently. That requires a different interface and more careful output design.

---

## Summary

The system works. An investigative journalist can now query fifteen years of his own reporting through Slack, get meaningfully relevant results, identify patterns across time, and get drafting help that will not invent facts. That is more than the assignment required and something I will continue to use.

The failures documented here were real, cost real time, and in two cases (verdict language, skill resolution) changed the architecture of the system. Documenting them honestly is the point: a system that worked despite bad assumptions about how the framework behaved, a model that ignored explicit instructions until the task was redesigned around its actual capabilities, and a resumable script that was not tested against the failure it was designed to handle. These are not unusual problems in AI systems development. They are typical. The more useful thing to say about them is not that they happened, but what they indicate about how to build more carefully next time.
