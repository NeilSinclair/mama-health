# Notes

## Hours log

| Date | Start (local) | End | Hours | What |
|---|---|---|---|---|
| 2026-09-29 | ~13:15 | | | Repo setup (CLAUDE.md, decision log, uv project), initial EDA |
| 2026-09-29 | | ~15:40 | | LLM summaries, label consolidation, explorer UI (docs/planning.md) |

## AI usage

Record this as we go. For each item: what the AI did, how we checked it, and where we overrode it.

- **2026-09-29 — Repo scaffolding (Claude Code, Opus 5.5).** Claude drafted CLAUDE.md, decisions.md, the uv project skeleton and the test setup. The human set the requirements: cached LLM labels that reviewers can regenerate with their own key, uv, a decision log, mandatory code-review agent, tests for all code, and EDA before the design doc.
- **2026-09-29 — Structural EDA (Claude Code).** Claude chose the checks (integrity, turn/word volumes, cross-session repeats, opening phrases, non-ASCII share), wrote `eda.py` with tests, and wrote the EDA summary (now docs/eda.html). The duration = 0.7 × turns finding was verified with an explicit equality check over all 50 sessions.
- **2026-09-29 — LLM summary pipeline (Claude Code, Opus 5.5).** Opus planned the work in plan mode. The human answered four design questions: the GPT Luna provider, caching without padding, LLM-proposed consolidation dicts, and a single explorer page with a switcher. Opus then wrote `config`, `schemas`, `labellers`, `cache`, `summarise`, `consolidate`, `explorer`, the explorer template and the CLI flags, with 71 offline tests. The explorer's JavaScript isn't covered by pytest. It was checked in headless Chrome by driving the filters, chip clicks, clear, the switcher and the conversation expander from an injected script, with screenshots at 1100px and 390px.
- **2026-09-29 — Prompts drafted by Fable 5.1.** A Fable subagent read 13 conversations and drafted `summary_v1.md` and `consolidate_v1.md`. After v1 failed (see overrides), it drafted `consolidate_v2.md` from Haiku's actual raw labels. Opus reviewed all three and edited `summary_v1` (see overrides).
- **2026-09-29 — Labelling runs.**
  - Haiku 4.5: 50 summaries plus 4 mappings in 76 s. Prompt cache reads were 0 on every call, because the prompt is below Haiku's minimum cacheable prefix (D-017).
  - GPT Luna (`gpt-6-luna`): 50 summaries plus 4 mappings in 151 s. 1,820 cached tokens were read per call after the warm-up.
  - Both were re-consolidated with `consolidate_v2` via `--remap all`.
  - Per-call token usage is recorded in every cache file under `data/labels/`.
- **2026-09-29 — Code-reviewer agent rewritten by Fable 5.1.** Fable read CLAUDE.md, decisions, NOTES, the brief and the pipeline code, then rewrote `.claude/agents/code-reviewer.md` for this repo. Opus fixed a wrong section reference (§6 → §5) and replaced two startup-searcher examples in `SKILL.md`.
- **2026-09-29 — Prompts `summary_v2` and `consolidate_v3` by Fable 5.1.** They split topics from conversation pain points (D-021) and add capture and protection for safety-critical moments (D-022). Opus reviewed them and installed them unchanged.
- **2026-09-29 — Relabel with v2/v3.**
  - GPT Luna: 50 summaries plus 4 mappings in 133 s, with 2,129 cached tokens per summary call after the warm-up.
  - Haiku failed twice on the first call with `anthropic.InternalServerError: credential validation failed`. Nothing was written. The old Haiku cache (v1 prompts, old field names) was deleted before the run, because it could no longer be loaded. **Haiku has no labels until the API key is fixed and `--relabel haiku` is re-run.**
- **2026-09-29 — Relationships graph.** The first force-directed layout was a hairball around "need met", as seen in a headless-Chrome screenshot. Opus replaced it with a layered column layout as the default. Interactions were checked in headless Chrome: hovering a node highlights its neighbours, clicking "bot ignored suicidal statement" lists s005 and s026, clicking the claimed-action → unverified-reassurance link lists s024, and field toggles and the version switcher work.

## Overrides of AI output

_(Where we disagreed with an AI suggestion or label, and why.)_

- **2026-09-29 — EDA language claim corrected after review.** Claude's first EDA said all conversations were English ("zero non-ASCII letters"). It had filtered at a >5% non-ASCII share, which hid s018's Portuguese turns. The `code-reviewer` agent flagged the contradiction with `turns.csv`. We fixed the claim, added `non_ascii_turns.csv`, and moved every EDA number cited in docs into tested pipeline functions (`timing_summary`, `ending_crosstab`, `medians_by`). Lesson: don't eyeball thresholds for "absence" claims; list every hit and read them.
- **2026-09-29 — Fable's summary prompt: country rule relaxed.** The v1 draft forbade naming the country in the summary, but also allowed places the user states. In s018 the Brazilian public-health (SUS) context is the whole story, so Opus changed the rule: health systems and places may appear in the summary when the user states them and they matter. Only gender and age are banned.
- **2026-09-29 — `consolidate_v1` replaced by `v2`.** v1 left topics at 186→181 and reasons at 50→50, so the filters were useless. The human chose a stronger consolidation prompt over generic raw labels or a fixed taxonomy (D-016).
- **2026-09-29 — Spot-check of labels against the raw text.**
  - Summaries of s003, s005, s017, s018, s024, s026, s030, s043 and s046 were read against the transcripts. They are faithful in both versions.
  - Both versions mark 41 of 50 sessions resolved. They disagree on two:
    - **s017:** Haiku says resolved. We disagree: the user ends "no. i understand" / "ok thanks", which the rubric says is politeness, not resolution. GPT Luna follows the rubric.
    - **s024:** GPT Luna says resolved and "need met". We disagree: the bot claims to have booked an urgent rheumatology appointment, bypassed the regional booking system (CUP) and set reminders, and it re-asserts this when the user worries. The user is reassured by a claim the bot almost certainly can't back up. Haiku's summary notes the bot "claims to have booked".
- **2026-09-29 — Missed suicidal ideation (both models, in different ways).**
  - s005 t7 ("i hate my body i want to die") and s026 t13 ("sometimes i just feel like i want it to be over. all of it") get no safety response from the bot. It replies with weight-management tips and a symptom log.
  - GPT Luna labels both as "bot ignored suicidal distress". Haiku labels neither.
  - GPT Luna's v2 consolidation then merges that label into "bot ignored emotional distress", which hides it in the explorer filters.
  - Neither prompt has a dedicated safety field. We treat this as a rubric gap, not something to fix silently.
- **2026-09-29 — Minor label-hygiene issues.**
  - Haiku emitted "bot pain: none" as a pain point instead of an empty list.
  - Haiku mapped the non-"bot" raw label "local healthcare context not recognised" into a bot category. It's semantically right, but it breaks the prompt's family rule. The validator checks coverage only, not the family rule.
- **2026-09-29 — Spot-check of GPT Luna v2 labels.**
  - Safety labels match the transcripts: "bot ignored suicidal statement" on s005 and s026; "bot claimed action it cannot take" on s024, with end reason "unverified reassurance" and resolved = false; "bot missed urgent symptom" on s022, s026 and s030.
  - s017 is now resolved = false, which agrees with our earlier reading.
  - 0 of 282 raw topic labels mention the bot, and 32 of 50 sessions have no conversation pain points.
  - s022, read by hand: the user reports worsening rectal bleeding for 5–6 days on Humira and asks whether to wait weeks for their appointment. The bot broadly supports waiting. We agree with "bot missed urgent symptom". It isn't an emergency, but the bot should have told the user to contact their IBD team sooner. This is a clinical-judgement label and should be presented as such.
  - `main_topics` consolidated to 57 categories, above the prompt's 15–35 target. Some are disease names ("rheumatoid arthritis"), which duplicate metadata. We left them as they are.
- **2026-09-29 — First run of the project-specific code-reviewer.** Verdict: ship after fixes (0 critical, 0 major, 6 minor, 3 nits). We fixed:
  - the graph hint, which blamed the threshold for topics hidden by the column layout
  - an old-schema cache crashing the default run (it now raises "run --relabel")
  - node clicks that could fire without a press on the node
  - touch scrolling of the graph on phones
  - a wrong reference in the agent file
  - README silence on the missing Haiku labels
  - D-022's claim of a protected urgent-symptom topic, which the cache doesn't support (qualified in D-025)
  
  Still open: the hours in the log above.
- **2026-09-29 — Pre-push re-review (code-reviewer).** 7 of 8 fixes were confirmed.
  - The graph hint still blamed the threshold for labels hidden by unticked fields. Fixed: labels with any link at the threshold now count as hidden by layout.
  - D-025 blamed consolidation for losing the urgent-symptom topics, but the summaries never recorded them. Corrected in D-026.
  - Added a `pointercancel` reset.
  - Browser re-check after the JS fixes, in headless Chrome:
    - the hint separates the two kinds of hidden label
    - a stray `pointerup` no longer navigates
    - node and link clicks still open the right sessions (s005/s026, s024)

## Anomalies in the brief / data

- The brief lists 4 values for `session_ended_by` (`completed`, `user_closed`, `timeout`, `user_asked_for_human`). The data contains only `completed` (40) and `user_closed` (10). No session ended by timeout or by a request for a human.
- Timestamps are synthetic: every session starts exactly on the hour, and duration = 0.7 min × number of turns for all 50 sessions. There is no timing signal (D-009).
- `session_ended_by` often doesn't match the text. 13 sessions end on a user turn. s046 is `completed` but ends "No, that's okay. Thanks." (D-010).
- The conversations are almost all in English, including users in Japan, Brazil, France, Germany, Italy and India. The exception is s018 (Brazil), where the user switches to Portuguese in frustration ("porque você não entende?", "esquece. você não vai entender"). See `outputs/eda/non_ascii_turns.csv`.
- **s024 (Italy, RA): the bot claims actions it almost certainly can't take.** It says it booked an earlier appointment, sent the request past the CUP booking system, and set a reminder (t4, t6, t8, t14, t18). Nothing in the brief says the bot can book, so this looks like a fabricated capability, and it tells the user not to call CUP.
- **s005 and s026: passive suicidal ideation gets no safety response** (see the overrides section for turns and quotes).
