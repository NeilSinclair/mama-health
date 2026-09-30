# Decision log

Append-only. Each entry records the decision, its rationale, the alternatives considered, and what would change it. To reverse a decision, add a new entry marked "Supersedes D-xxx"; don't edit the old one.

---

### D-001 — Cache LLM labels in the repo; allow reviewers to regenerate with their own key
- **Date:** 2026-09-29
- **Decision:** Qualitative labels produced by an LLM are cached in `data/labels/` and committed. The pipeline reads the cache by default, with no API calls. Reviewers can put their own `ANTHROPIC_API_KEY` in `.env` and rerun labelling.
- **Rationale:** The brief requires reviewers to reproduce every number. Live LLM calls need a key, cost money, and aren't deterministic. Caching makes the default path reproducible, and the relabel path keeps it honest.
- **Alternatives:** (a) Deterministic methods only (keywords, heuristics): reproducible but weak on judgement-heavy measures like safety and emotional register. (b) Live LLM calls only: not reproducible without a key.
- **Would change if:** The reviewers said they won't run anything requiring a key *and* distrust cached labels. In that case we'd add a heuristic baseline alongside the LLM labels.

### D-002 — Use uv for environment and dependency management
- **Date:** 2026-09-29
- **Decision:** `uv` with `pyproject.toml` and a committed `uv.lock`. Python pinned via `.python-version`.
- **Rationale:** User preference. It also gives a one-command, locked, reproducible setup (`uv sync`), which serves the brief's "≤ 3 commands" constraint.
- **Alternatives:** pip + venv + requirements.txt; conda.

### D-003 — Maintain a decision log (this file)
- **Date:** 2026-09-29
- **Decision:** Every scope, methodology, definition, metric and tooling decision is logged here.
- **Rationale:** The brief grades *what we chose* to measure and *what we refused to claim*. A running log makes those choices explicit and feeds the memo and NOTES.md directly.

### D-004 — Mandatory code review by an agent before every push and PR merge
- **Date:** 2026-09-29
- **Decision:** A code-review agent (to be created by the user in `.claude/agents/`) must review the diff before every `git push` and every PR merge. The rule is recorded in CLAUDE.md.
- **Rationale:** Correctness of the pipeline underpins every claim in the memo, and the brief discounts any claim we can't reproduce.

### D-005 — Tests required for all code
- **Date:** 2026-09-29
- **Decision:** Every module in `src/` has pytest tests. Tests run offline and never call the LLM API.
- **Rationale:** Reproducibility and trust in the numbers. Offline tests keep CI and reviewer runs free and deterministic.

### D-006 — Package layout: `src/mama_analysis`, plain Python modules, single CLI entry point
- **Date:** 2026-09-29
- **Decision:** The pipeline is an installable package (`src/mama_analysis`) exposed as `uv run mama-pipeline`. Numbers in the memo come from package code, not notebooks.
- **Rationale:** Notebooks are hard to test and to run headless. A single entry point keeps the reviewer path to `git clone` → `uv sync` → `uv run mama-pipeline`.
- **Alternatives:** Notebook-driven analysis; Makefile orchestration.
- **Would change if:** The user prefers notebooks for narrative exploration. That's fine for EDA, as long as memo numbers still come from the package.

### D-007 — Log AI usage and hours in NOTES.md as we go
- **Date:** 2026-09-29
- **Decision:** `NOTES.md` holds a running AI-usage/override log, an hours log and an anomalies list.
- **Rationale:** The brief explicitly asks for these and says it treats hours as data. A retrospective reconstruction would be less accurate.

### D-008 — Sequence: EDA before the design document
- **Date:** 2026-09-29
- **Decision:** Start with exploratory data analysis. The user will then write a design document informed by it, before the main pipeline is built.
- **Rationale:** What "working" means, and which measures matter, should be grounded in what the data actually contains.

### D-009 — Don't use timestamps as a behavioural signal
- **Date:** 2026-09-29
- **Decision:** Session duration, time of day and turn timing are excluded from any engagement or "working" metric.
- **Rationale:** EDA shows every session starts exactly on the hour and `duration = 0.7 min × n_turns` for all 50 sessions. The timestamps are generated, so they carry no information beyond turn count. They're UTC with no user timezone, so local time of day isn't recoverable either. See docs/eda.html.
- **Would change if:** We got real timestamps, or learned they encode something real (e.g. reply latency).

### D-010 — Treat `session_ended_by` as a weak signal, not the outcome
- **Date:** 2026-09-29
- **Decision:** `session_ended_by` won't be used alone as the success/outcome variable. Conversation endings are judged from the text.
- **Rationale:** Only 2 of the 4 documented values occur. 13 sessions end on a user turn. Some `completed` sessions end with a disengaged-sounding user (s046) and some `user_closed` ones end after a clear bot failure (s030). The label is *how*, not *why*, as the brief itself warns.

### D-011 — Commit generated outputs
- **Date:** 2026-09-29
- **Decision:** `outputs/` is committed alongside code.
- **Rationale:** The memo cites files in `outputs/`, so a reader can follow citations without running anything. The pipeline regenerates them identically, which checks reproducibility.
- **Alternatives:** gitignore `outputs/` and have reviewers generate them.

### D-012 — Discussion documents are written as HTML
- **Date:** 2026-09-29
- **Decision:** Documents for the user and Claude to discuss (EDA write-ups, findings, design notes, comparisons) go in `docs/` as self-contained `.html` files. Submission files (`MEMO.md`, `README.md`, `NOTES.md`, `decisions.md`, `CLAUDE.md`) stay Markdown. `docs/eda.md` was converted to `docs/eda.html`.
- **Rationale:** User preference: HTML reads better for discussion (cards, tables, callouts). The brief specifies Markdown or PDF for the memo, so submission files keep that format.
- **Would change if:** A discussion doc gets promoted into the submission. It would then be rewritten as Markdown.

### D-013 — Google-style docstrings, enforced by ruff
- **Date:** 2026-09-29
- **Decision:** Every public module, class and function in `src/` has a Google-style docstring (`Args:` / `Returns:` / `Raises:`). Ruff's `D` rules run with `convention = "google"`; `tests/` is exempt.
- **Rationale:** User preference. Consistent docstrings make the pipeline easier for reviewers to follow, and lint enforcement stops drift.
- **Note:** Ruff flags missing docstrings and malformed sections but not missing `Args:` sections, so completeness still relies on review.

### D-014 — Two labelling models, user picks the winner
- **Date:** 2026-09-29
- **Decision:** Conversation summaries and label mappings are produced twice, with identical prompts: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) and OpenAI GPT Luna (`gpt-6-luna`). Both caches are committed, and the explorer has a switcher. The user judges which version the memo uses.
- **Rationale:** User request (docs/planning.md). Running both on the same prompts makes the differences a model effect, not a prompt effect.
- **Would change if:** Once a winner is chosen, the other version may be dropped from the pipeline or kept as a robustness check.

### D-015 — Metadata is copied, never inferred by the LLM
- **Date:** 2026-09-29
- **Decision:** Disease, age group, gender, country and `session_ended_by` are copied from the dataset into each summary (`summarise.merge_deterministic`). The rendered transcript sent to the model contains no metadata. The model's `end_reason` sits alongside the logged `session_ended_by`; it doesn't replace it.
- **Rationale:** The spec asks for a "deterministic copy". Leaving metadata out of the prompt also stops the model's labels from leaning on demographics.

### D-016 — Label consolidation: LLM-proposed dictionary, cached and validated
- **Date:** 2026-09-29
- **Decision:** For each version and field (`main_topics`, `pain_points`, `reason_for_conversation`, `end_reason`), the same model gets every unique raw label and returns a raw→canonical mapping. Code checks that every raw label is mapped exactly once (retrying up to 3 times), then caches the mapping in `data/labels/mappings/<version>/`. Raw labels are kept and shown on hover in the explorer.
- **Superseded detail:** `consolidate_v1` barely merged anything with Haiku (topics 186→181, reasons 50→50). The raw labels were specific, and v1's "don't force merges" was read as "map to self". v2 (the current version) asks for the category a product manager would filter on, targets 10–30 categories, and makes singletons rare. Result: Haiku topics 186→40, reasons 50→12; GPT Luna topics 205→30, pain points 180→32.
- **Alternatives:** A hand-written dictionary (can't be regenerated by reviewers); a fixed taxonomy (departs from the spec's free-text-then-map design).
- **Known gap:** v2 lets GPT Luna merge "bot ignored suicidal distress" into "bot ignored emotional distress". Safety-critical labels need their own protected category (see NOTES, overrides).

### D-017 — Prompt caching: warm-up call, then async; no padding
- **Date:** 2026-09-29
- **Decision:** The shared system prompt is marked `cache_control` (Anthropic) or cached automatically with a stable `prompt_cache_key` (OpenAI). The first call runs alone to write the cache, then the rest run concurrently (8 in flight). Cache-read tokens are logged in every cache entry.
- **Result:** OpenAI read 1,820 cached tokens on every summary call after the warm-up. Haiku cached nothing: our prompt is below Haiku 4.5's minimum cacheable prefix. We chose not to pad the prompt to cross the threshold (user decision), because padding changes the outputs.

### D-018 — Structured outputs via pydantic; reproducibility comes from the cache
- **Date:** 2026-09-29
- **Decision:** Outputs are pydantic models (`schemas.SummaryLLM`, `schemas.LabelMapping`) enforced by the API: `messages.parse(output_format=...)` and `responses.parse(text_format=...)`. No temperature is set; the Anthropic SDK's `parse` doesn't expose it, and reasoning models ignore it. Reproducibility comes from the committed cache, not from deterministic sampling. Each entry records the model ID, prompt version, prompt SHA-256 and a timestamp, and the pipeline warns when entries are stale.

### D-019 — Explorer is a generated pipeline output
- **Date:** 2026-09-29
- **Decision:** `outputs/explorer.html` is built by `uv run mama-pipeline` from cached labels: a single self-contained page with the JSON embedded. It's byte-deterministic and covered by the committed-outputs drift test. The template lives at `src/mama_analysis/templates/explorer.html`.
- **Rationale:** It's an analysis output the memo can point to, not a discussion doc, so it belongs in `outputs/` (D-011), not `docs/`.

### D-020 — Prompts drafted by Fable, reviewed by Opus
- **Date:** 2026-09-29
- **Decision:** Per docs/planning.md, Claude Fable 5.1 drafts the LLM prompts and Claude Opus 5.5 writes the code and runs the code review. Prompts are versioned files in `src/mama_analysis/prompts/`. Old versions stay in the repo and new versions get new filenames.

### D-021 — Topics hold what the user talks about; conversation pain points hold only bot failures
- **Date:** 2026-09-29
- **Decision:** `pain_points` is renamed `conversation_pain_points` and now holds only problems the user had *with the conversation*: things the bot did or failed to do, phrased "bot …", or an empty list. Everything the user talks about, including their health issues and care-system hardships (dismissive doctors, waits, cost), goes under `main_topics`. Prompts: `summary_v2`, `consolidate_v3`.
- **Rationale:** User request. The old field mixed "why the user is struggling" with "where the bot let them down", so it couldn't answer the product question.
- **Supersedes:** the `pain_points` field of D-016. The consolidation method is unchanged.

### D-022 — Safety-critical moments are always captured and never merged
- **Date:** 2026-09-29
- **Decision:** `summary_v2` must capture every suicidal or self-harm statement, every urgent symptom, and every bot claim of a real-world action it can't evidently take (booking, contacting a clinic, setting reminders). Mishandled cases get specific pain-point labels. `consolidate_v3` keeps "bot ignored suicidal statement", "bot missed urgent symptom" and "bot claimed action it cannot take" (and the topics "suicidal thoughts" / "urgent symptom") as protected categories that are never merged, even as singletons. `issue_resolved` is false when the user's relief rests on an unverified bot claim.
- **Rationale:** With `consolidate_v2`, GPT Luna merged s005/s026's "ignored suicidal distress" into "ignored emotional distress", which hid them from the filters (NOTES, overrides).
- **Assumption we can't verify:** the brief doesn't describe the bot's capabilities. We assume a chat companion can't book appointments or contact clinics. If mama health's bot can, s024 isn't a fabrication.

### D-023 — Relationships graph built from tested co-occurrence counts
- **Date:** 2026-09-29
- **Decision:** The explorer's Relationships tab is a network of canonical labels from `main_topics`, `conversation_pain_points` and `end_reason`. A link joins two labels from different fields that occur in the same session, weighted by the number of sessions. Nodes and links are computed in Python (`explorer.label_graph`, tested) and also written to `outputs/summaries/<version>/label_cooccurrence.csv`, so any relationship the memo cites is traceable. The default view is layered: one column per field, neighbouring columns linked only, ordered to reduce crossings. The free force layout is a toggle.
- **Rationale:** The user chose a network graph over a Sankey or a matrix. The first force layout was a hairball dominated by "need met", so columns are the default.
- **Caveat:** Sessions have several topics, so links count shared sessions, not flows. They don't add up to 50.

### D-024 — Project-specific code-reviewer agent
- **Date:** 2026-09-29
- **Decision:** `.claude/agents/code-reviewer.md` was rewritten for this repo (drafted by Fable 5.1, reviewed by Opus). It encodes the CLAUDE.md contract: raw data read-only, traceability, zero-API default run, cache provenance, versioned prompts, D-015 metadata copy, the partial-failure rules, the drift test, HTML safety, and the memo checklist. It runs on Opus and never runs `--relabel`/`--remap`. Two startup-searcher examples in `.claude/skills/code-reviewer/SKILL.md` were replaced.
- **Supersedes:** the prompt-override workaround used for the reviews recorded under D-004 so far.

### D-025 — Qualifies D-022: only the pain-point safety labels are reliably protected
- **Date:** 2026-09-29
- **Decision:** D-022's protection holds for the three `conversation_pain_points` safety labels (checked in the GPT Luna cache). It doesn't hold for topics: `consolidate_v3` asks for a protected `urgent symptom` topic, but GPT Luna folded s022/s026/s030's urgent symptoms into "bowel symptoms" and "migraine". Memo and filter claims about urgent symptoms therefore use the pain-point label "bot missed urgent symptom", not a topic. No code enforces protected categories. The validator checks coverage only.
- **Would change if:** A post-consolidation check (protected raw labels must map to their protected canonical) or a dedicated safety field in the summary schema.
- **Found by:** the project-specific code-reviewer agent (D-024), on its first run.

### D-026 — Corrects D-025's diagnosis: urgency was lost at the summary stage
- **Date:** 2026-09-29
- **Decision:** D-025 said consolidation folded the urgent-symptom topics away. The cache shows the raw `main_topics` for s022, s026 and s030 never mention urgency, so the summary stage lost it. A post-consolidation check (D-025's proposed fix) therefore wouldn't catch these. s034 is a further case: its raw "urgent symptom warning signs" became "urgent symptom concerns", not the protected "urgent symptom". D-025's conclusion stands: urgent-symptom claims use the pain-point label "bot missed urgent symptom", never a topic. A reliable fix would be a dedicated safety field in the summary schema.
- **Found by:** the code-reviewer agent's pre-push re-review.

### D-027 — Reason for conversation added to the Relationships graph (extends D-023)
- **Date:** 2026-09-30
- **Decision:** The graph now has four fields: `reason_for_conversation`, `main_topics`, `conversation_pain_points` and `end_reason`, in that column order. `label_graph`, and so `label_cooccurrence.csv`, now include reason links too.
- **Rationale:** The human asked for it. Reason goes first because it is why the user came, and it reads left to right into what they talked about, what went wrong and how it ended. With neighbour-only links, reasons link to topics. Unticking Topics links reasons to pain points directly.
- **Alternatives considered:** Putting reason next to end reason, to show reason → outcome directly. You can still get that view by unticking Topics and Pain points.
- **What would change it:** If the reason → end-reason view proves more useful than reason → topics, reorder the columns.

### D-028 — Clicking a graph label follows its conversations, not graph paths
- **Date:** 2026-09-30
- **Decision:** Clicking a label highlights every shown label and link used by at least one conversation that has the clicked label. Hover still highlights direct neighbours only. Clicking a link highlights just that link and its two ends.
- **Rationale:** The human wanted a reason to "link all the way" to end reasons. Following links outward column by column would highlight nearly everything, because shared topics link to many conversations. Following session IDs shows only what those conversations did. It also reaches end reasons when there is no pain point in between (32 of 50 GPT Luna sessions).
- **Caveat:** A highlighted link keeps its full width, which counts every session sharing both labels, not only the traced ones. The link tooltip lists its session IDs.
- **What would change it:** If users read highlighted link widths as traced counts, recompute widths for the traced subset.

### D-029 — Supersedes D-028: clicking a graph label pins its neighbour highlight again
- **Date:** 2026-09-30
- **Decision:** Clicking a label pins the same direct-neighbour highlight that hovering shows. The conversation-tracing highlight from D-028 is removed.
- **Rationale:** The human found the traced view very confusing to look at. Too much of the graph lights up to read.
- **Alternatives considered:** Keeping tracing but thinning the unrelated links. It would still highlight too much.
- **What would change it:** A clearer way to show one reason's path to its end reasons, e.g. a filtered view that hides the other labels instead of highlighting within the full graph.

### D-030 — GPT Luna is the labelling model; Haiku removed (supersedes D-014)
- **Date:** 2026-09-30
- **Decision:** The human chose GPT Luna (`gpt-6-luna`). The Haiku cache, the Haiku outputs, the Anthropic adapter and the `anthropic` dependency are removed. The explorer hides its model switcher when only one model is configured. The pipeline keeps its version-keyed layout (`data/labels/*/gpt_luna/`, `outputs/summaries/gpt_luna/`).
- **Rationale:** The bake-off in D-014 was done. Neither model was strictly better (see NOTES, 2026-09-30), and the human preferred GPT Luna. Code for a model nobody runs would be dead code.
- **Alternatives considered:** Keeping the Anthropic adapter for a future Claude run. It's recoverable from git history if needed.
- **What would change it:** A need for a second labeller, for example to measure labeller agreement.

### D-031 — Conversation pain points need evidence in the transcript; profile use is not a pain point (summary_v3)
- **Date:** 2026-09-30
- **Decision:** `summary_v3` (drafted by Fable, per D-020) tells the model:
  - The bot is given the user's profile (country, age group, gender, condition), so using those details is not a pain point.
  - A pain point needs transcript evidence that something went wrong: the user corrects, objects, pushes back, repeats or is frustrated; or there is an objective failure, such as a contradiction, an unanswered direct question, or a statement that conflicts with what the user said.
  - Safety-critical failures are still flagged whether or not the user complains.
- **Rationale:** The human reviewed v2's pain points. It flagged "bot assumed country context" for a user who does live in Canada and didn't object (s016), and similarly age (s007) and gender (s049). Meanwhile, the Brazil user frustrated by US insurance talk (s018) is a clear pain point.
- **Assumption:** The bot sees the user's profile. Evidence: in s007 the bot says "at 18-24", the profile's exact age bucket, which the user never states. The labelling model itself still doesn't see the metadata (D-015).
- **Counter-evidence:** In s014 (Japan), s018 (Brazil) and s042 (India), the bot gives US-centred advice despite the profile country. So either the bot doesn't always use the profile, or it ignores it. Either way, those sessions are pain points under this rule, because the user corrects the bot. The rule doesn't depend on the assumption being always true: it only stops flagging profile use the user accepts.
- **Alternatives considered:** Passing the user's metadata to the labelling model so it can check the bot's assumptions. Rejected for now: it reverses D-015, and the transcript rule handles the observed cases.
- **What would change it:** Spot-checks finding real pain points that v3 misses because the user didn't react.

### D-032 — A corrected mistake is still a pain point (summary_v4, refines D-031)
- **Date:** 2026-09-30
- **Decision:** `summary_v4` adds one rule to v3's pain-point section: a user's correction counts even when the bot then apologises and adapts, because the user still had to catch the mistake.
- **Rationale:** v3 dropped s042. There the bot pointed a user in India to US resources, the user noticed, and the bot adapted. The human wants that kept as a pain point.
- **Alternatives considered:** Editing v3 in place. Rejected, because NOTES' v2→v3 spot-check describes v3's output, and a new version keeps that traceable. The v3 labels themselves were overwritten by the v4 run, so they're a record in NOTES, not reproducible outputs.
- **What would change it:** Nothing pending.

### D-033 — Topics are scored for relevance; only strong topics are used (summary_v5)
- **Date:** 2026-09-30
- **Decision:**
  - `main_topics` is now a list of `{topic, reason, relevance}`, with relevance one of strong, medium or low. The model writes the reason before the score.
  - There is no target number of topics. `summary_v5` (drafted by Fable, per D-020) defines the levels and asks for at least one strong topic, usually one to three.
  - Only strong topics go on to consolidation, the explorer chips and filters, the graph, `label_counts.csv` and `label_cooccurrence.csv`. `consolidate.field_labels` is the single place this filter is applied. (Superseded by D-035: all topics are now consolidated and `shown_labels` applies the filter.)
  - Medium and low topics stay in the cache, in `summaries.csv` (`topic_scores`) and in the explorer's "Topic scores" section.
- **Rationale:** The human found the topics too noisy. v4 averaged 5.9 topics per session and 41 canonical topics, many of them passing mentions. With v5 it was 1.5 strong topics per session and 35 canonical topics. Those figures come from the v5 run, which the v6 relabel overwrote, so they aren't reproducible from the committed cache.
- **Consequence:** A safety-critical topic can be scored below strong and drop out of the topic chips. In the v5 run, s005's "suicidal thoughts" was medium; in the committed v6 cache it is low. Safety is still carried by `summary` and `conversation_pain_points` (D-022, D-026). s005 keeps "bot ignored suicidal statement".
- **Alternatives considered:** A hard cap on the number of topics. Rejected, because the human wanted the model free to choose how many. Always keeping safety-critical topics regardless of score was not done; it's for the human to decide.
- **What would change it:** Strong-only topics hiding things the analysis needs. The fix would be to lower the threshold (`KEPT_RELEVANCE`) or add a safety exception.

### D-034 — End reason is a fixed three-value vocabulary (summary_v6)
- **Date:** 2026-09-30
- **Decision:**
  - `end_reason` must be one of `need met`, `partial resolution` or `unresolved need`. It's enforced by the schema, as a `Literal` in the structured output, and defined in `summary_v6`.
  - `need met` pairs with `issue_resolved = true`; the other two pair with `false`.
  - End reason is no longer sent for LLM consolidation (`consolidate.CONSOLIDATED_FIELDS`). Its labels map to themselves, and the cached `end_reason.json` mapping was deleted.
- **Rationale:** The human asked for exactly these three. The open vocabulary gave seven overlapping labels ("left unheard", "gave up frustrated", "natural close", …). How a conversation went wrong is already recorded in `summary` and `conversation_pain_points`.
- **Alternatives considered:** Keeping the open vocabulary and consolidating it to three categories. Rejected: a schema-enforced enum can't drift, and it saves a consolidation call.
- **What would change it:** A need to tell apart kinds of unresolved endings (e.g. gave up vs. unverified reassurance) in the outputs rather than in pain points.

### D-035 — All topics are consolidated; the strong filter is applied after mapping (supersedes D-033's consolidation scope)
- **Date:** 2026-09-30
- **Decision:**
  - Every scored topic (strong, medium and low) goes into one `main_topics` consolidation (`consolidate.field_labels`).
  - Only strong topics become chips, counts, graph nodes and co-occurrence rows (`consolidate.shown_labels`).
  - The explorer's "Topic scores" list and the `topic_scores` column now show each topic's canonical label, with the raw topic kept alongside.
- **Rationale:** The human wanted the non-strong topics simplified to generic topics too. A single shared vocabulary means a topic gets the same canonical label whatever its score in a given session. Separate vocabularies per relevance level would not.
- **Effect:** 306 raw topics became 71 canonical ones (strong: 81 → 45). The strong-topic vocabulary shifted from 42 labels (strong-only consolidation of the v6 summaries, overwritten by this remap) to 45, because the model now groups them alongside the medium and low topics.
- **Alternatives considered:** A second mapping just for medium and low topics. Rejected for the inconsistency above.
- **What would change it:** If 71 canonical topics is still too many (the `consolidate_v3` target is 15–35), tighten the topic consolidation prompt.

### D-036 — Breakdown tab: linked counts; field colours re-validated
- **Date:** 2026-09-30
- **Decision:**
  - The explorer gets a third tab, Breakdown. It has one bar list of conversation counts per field: reason for conversation, topic, conversation pain point, end reason, resolved and disease.
  - Clicking a bar keeps only conversations with that label, and every list recounts. Selections combine with AND, and clicking again removes one.
  - A toggle switches the topic counts from strong only (the default) to all scored topics, by canonical label. Empty pain-point lists count as "(none)".
  - The matching conversations are listed below, with the first sentence of each summary.
  - These choices come from the human's answers.
  - Separately, the field colours were changed after the dataviz palette validator failed the existing set:
    - The reason purple (added in D-027) was hard to tell from the topic blue, even with normal vision.
    - The dark-mode salmon and green (pain point vs end reason) were not colour-blind-safe.
  - New colours: light reason `#a8408f`; dark `#c064bc` / `#5f8ce0` / `#dd6e58` / `#34a595`. They pass every check across all pairs in both modes. The remaining CVD warning is in the 6–8 band, which is allowed because every panel and graph column is text-labelled.
- **Rationale:** The human wanted to click a topic and see counts of reasons, topics and end reasons for it. Linked counts answer that for any field, and for combinations. The counts are computed in the page from the same payload as `label_counts.csv`. They are for exploration; memo numbers still come from pipeline CSVs.
- **Alternatives considered:** A pivot table (only two fields at a time) and a single-label drill-down card (one label at a time). The human chose linked counts.
- **What would change it:** If the memo cites a cross-count from this tab, add it as a tested pipeline table first (CLAUDE.md traceability rule).

### D-037 — Conversation-dynamics pass and analysis tables; definitions fixed before the run
- **Date:** 2026-09-30
- **Decision:**
  - There's a separate LLM pass, `dynamics_v1`, drafted by Fable per D-020, with its own cache in `data/labels/dynamics/`. It labels each session's `final_sentiment` (satisfied, neutral or dissatisfied; how the user *sounded*, not whether the need was met) with a verbatim quote, plus every `pushback`: a user turn resisting the bot's previous reply, with its kind, quote, and whether the bot's **next** reply adapted.
  - Every quote is checked against its transcript turn (`dynamics.check_dynamics`). Failures are reported, not dropped.
  - `analysis.py` builds `outputs/analysis/<version>/`: `ending_vs_outcome`, `ending_mismatches`, `sentiment_vs_outcome`, `silent_failures`, `pushbacks`, `recovery_by_outcome` and `friction`.
  - The silent-failure rule was fixed before the run: `final_sentiment == satisfied` and (end reason ≠ need met, or a safety pain point).
  - `--dynamics <version>` re-runs only this pass. `--relabel` includes it.
- **Rationale:** The human asked for three analyses:
  - whether the product's logged "completed" hides failures
  - failures the user didn't notice
  - what happens after users push back

  A separate pass keeps the checked summary labels unchanged; adding fields to the summary would have meant relabelling everything, and we've seen that shift labels.
- **Alternatives considered:**
  - Adding fields to the summary schema; rejected for the label churn above.
  - A regex-based pushback detector; too brittle for "you keep saying that" vs a new question.
  - A broader silent-failure rule, counting any pain point; not chosen, to keep it to outcome and safety.
- **Caveats:**
  - The same model judges "adapted" (this pass) and the outcome (summary pass). They're separate calls, but a model may judge adaptation less generously in conversations that end badly, so the two are not fully independent.
  - n = 50, synthetic.
- **What would change it:**
  - A hand-labelled check disagreeing with `bot_adapted` on the key sessions.
  - Pushback labels proving unstable across re-runs.

