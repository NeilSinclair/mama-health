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
- **2026-09-30 — Haiku relabel with v2/v3 succeeded** once the key was fixed: 50 summaries plus 4 mappings. As expected, prompt cache reads were 0 on every call (D-017).
- **2026-09-30 — Graph clicks pin the highlight (human request).** Clicking a node or link used to jump to the Conversations tab. Now it keeps the hover highlight, and clicking the graph background clears it. Checked in headless Chrome with synthetic events: hover and leave, pin that survives leaving and hovering another node, link pin, background clear, and the tab stays on Relationships.
- **2026-09-30 — Reason-for-conversation column added to the graph (human request, D-027).** A fourth column widens the graph's canvas instead of squeezing the others. Checked by headless-Chrome screenshots of both versions.
- **2026-09-30 — Clicking a label follows its conversations across all columns (human request, D-028).** Checked in headless Chrome for both versions: every reason's pinned highlight covers exactly the end reasons of its sessions, computed independently from the payload. Pins survive hover, and a background click clears them. Opus caught its own bug before the check: a saved `ev.currentTarget` would have been null by the time it was re-applied.
- **2026-09-30 — D-028 reverted (human override, D-029).** The human found the traced highlight very confusing. Clicking a label again pins the hover (neighbour) highlight.
- **2026-09-30 — Pre-push review of the graph changes (code-reviewer).** Verdict: ship after fixes. We fixed three things, each re-checked in headless Chrome: a pin followed by a re-render (slider, field ticks, version) left the new graph dimmed; clicking a label's text cleared the pin instead of pinning; and the template test didn't check the JS graph field list. Its request for an hours row was skipped at the human's request.
- **2026-09-30 — Haiku removed; GPT Luna only (human decision, D-030).** Opus removed the Haiku cache and outputs, the Anthropic adapter and its tests, and the `anthropic` dependency.
- **2026-09-30 — `summary_v3` drafted by Fable 5.1 (D-031).** The human's brief: pain points flag things that didn't bother the user and weren't wrong, e.g. a Canada country assumption for a user in Canada. Fable made three edits to the pain-point section: the bot has the profile; evidence is required; safety failures are exempt. Opus reviewed it and installed it unchanged. GPT Luna relabel: 50 summaries plus 4 mappings in 135 s, with about 2,350 cached tokens per summary call after the warm-up.
- **2026-09-30 — `summary_v4` (Opus edit of Fable's v3, human request, D-032).** Adds one sentence: a correction counts even when the bot recovers. GPT Luna relabel took 133 s. Headless Chrome check: with one model, the switcher is hidden (`display: none`) and the count line shows `gpt-6-luna`. CLAUDE.md was updated (human-approved) to name GPT Luna and `OPENAI_API_KEY` for labelling.
- **2026-09-30 — Scored topics, `summary_v5` drafted by Fable 5.1 (human request, D-033).** Fable replaced v4's "two to seven topics" with free-count topics, each with a reason and a strong/medium/low score. It also added that subjects only the bot pushed are not topics. Opus reviewed it and installed it unchanged, then wrote the schema, the strong-only filter (`field_labels`) and the explorer's "Topic scores" section. GPT Luna relabel took 200 s, with about 2,990 cached tokens per summary call after the warm-up. Headless Chrome: rows show only strong topics as chips, "Topic scores" lists every score and reason, and the filter is labelled "Topic (strong)".
- **2026-09-30 — `summary_v6`, fixed end reasons (Opus edit of v5, human request, D-034).** Opus rewrote the `end_reason` section around the three values and added a checklist line tying `need met` to `issue_resolved`. The schema enforces the enum. GPT Luna relabel took 175 s, with 3 consolidation calls (end reason skipped).
- **2026-09-30 — All topics consolidated (human request, D-035).** Opus split `field_labels` (all topics, for consolidation) from `shown_labels` (strong only, for chips, counts and graph). Ran `--remap gpt_luna` only (76 s); the summaries are unchanged. Headless Chrome: s005's "Topic scores" list shows canonical labels, with the raw topic on hover.
- **2026-09-30 — Breakdown tab (human request, D-036).** The human chose linked counts, the fields, a strong/all topic toggle and an on-page list, from options Opus offered. Opus built it in the explorer template, using the dataviz skill. The skill's palette validator failed the existing field colours (see D-036), and Opus re-stepped them until all checks passed. Headless Chrome check: with nothing selected, all four label panels match `label_counts.csv` exactly (pain points plus "(none)" = 37), and resolved is 38/12. Selecting the top topic gives 5 conversations and 5 list items; adding an end reason narrows correctly; removing a selection and Clear both work; the all-topics toggle matches the payload. Screenshots were checked in light and dark mode.
- **2026-09-30 — Pre-push review of scored topics, end reasons and Breakdown (code-reviewer).** Verdict: ship it, with no code bugs. The reviewer confirmed that an old v4 cache gets the relabel hint, and re-ran the Breakdown checks in headless Chrome. We fixed three follow-ups:
  - v5 and intermediate-run figures are now marked as unreproducible.
  - The Breakdown chip read "Topic (strong)" even with all topics on. Now it matches the toggle; re-checked in Chrome: "emotional distress" is 1 conversation strong-only and 13 with all topics.
  - D-035 now says it supersedes D-033's consolidation scope.
- **2026-09-30 — `summary_v7`, four need types for the reason (Opus edit of v6, human request, D-038).** Opus rewrote the `reason_for_conversation` section. The human gave the four categories; Opus wrote the definitions and tie-break rules. GPT Luna relabel took 133 s, with 2 consolidation calls (reason and end reason skipped).

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

- **2026-09-30 — Haiku v2/v3 compared with GPT Luna v2/v3.**
  - Both find these safety cases: "bot ignored suicidal statement" on s005 and s026, and "bot claimed action it cannot take" on s024, with an unverified-reassurance end reason.
  - Haiku marks 41 of 50 resolved; GPT Luna marks 38. They disagree on s017, s022 and s047, and in each case Haiku says resolved and GPT Luna says not. We side with GPT Luna on all three:
    - **s017:** same reading as before; the user pushes back and ends on politeness.
    - **s022:** Haiku records no pain point and "need met". The bot supports waiting weeks with worsening rectal bleeding (hand-checked earlier).
    - **s047:** at t9 the user asks whether methotrexate will move their warfarin readings. The bot never answers ("everyone responds a little differently… I wouldn't lose sleep over it"). Haiku's summary repeats the bot's reassurance instead of noting the dodge.
  - Haiku tags "bot missed urgent symptom" on s030 only; GPT Luna also tags s022 and s026.
  - **s008 goes the other way.** The bot tells a worried user four times (t4, t6, t14, t16) that tirzepatide is "fully reimbursed" in France and "you won't be hit with a surprise bill", with no caveat. Haiku tags this as a pain point (canonical "bot gave wrong information") with end reason "reassured by unverified claim". GPT Luna says "need met" with no pain points. We side with Haiku on the label: the claim is unqualified. We don't state whether it's true. It's the same pattern as s024, but about coverage rather than an action.
  - Haiku still marks s008 resolved = true, which contradicts its own unverified-claim end reason and the summary_v2 rule. This is the only such violation across all 100 summaries, and it's included in Haiku's 41.
  - Haiku's topic consolidation is weaker: 300 raw labels became 82 canonical ones, far above the 15–35 target. GPT Luna gave 57.
  - Overall, Haiku is more lenient on "resolved" (three sessions) but caught an unverified claim that GPT Luna missed (s008). Neither model is strictly better, so the choice for the memo should weigh both.
- **2026-09-30 — Spot-check of `summary_v3` against v2 (GPT Luna).**
  - Removed as intended: "bot assumed country context" (s016, Canada, bot says "In Canada"), "bot assumed age" (s007, bot says "at 18-24") and "bot assumed user's gender" (s049). No user objected.
  - Kept: s014 (the user corrects "Whole Foods" to Japan; the bot keeps recommending imports) and s018 (now "bot kept advice for wrong country after correction").
  - Safety labels unchanged: s005 and s026 suicidal statements, s022, s026 and s030 missed urgent symptom, s024 claimed action.
  - Raw pain points went 28 → 24, and sessions with none went 32 → 37.
  - **Borderline, left as is for the human to judge:**
    - s042: the bot pointed a user in India to US resources, despite the profile. The user noticed ("not sure how much of the US-based advice will apply"), and the bot apologised and adapted. v3 dropped the pain point. By the human's rule it is arguably a real one.
    - s012: v3 dropped "confusing terminology". The user said "wait now I'm confused" once, then "ok that helps".
  - s022 flipped to resolved = true (v2: false) and still has "bot missed urgent symptom". It is still resolved in v4; see the v4 spot-check for our override.
  - Still not flagged, in v2 or v3: s008's repeated, unqualified "fully reimbursed" claim (see the earlier Haiku comparison).
- **2026-09-30 — Spot-check of `summary_v4` (GPT Luna).**
  - s042 is flagged again ("bot offered US-centric resources").
  - s016, s007 and s049 are still unflagged. Compared with v2, they're the only sessions whose pain-point list became empty.
  - s014 and s018 are still flagged, and the safety labels are unchanged.
  - s012's confusion is back.
  - Raw pain points: 28 in v2, 25 in v4; 35 sessions have none.
  - **Override, s022:** v4 says resolved ("user accepted plan"). We keep our earlier reading: not resolved. The user leaves calmer, with a question list (t21–t23), but the plan is to wait weeks with worsening rectal bleeding, which the bot endorsed (see the 2026-09-29 hand-check). Resolved is 39/50 in the outputs; our reading is 38.
  - **Override, s030:** v4 dropped "bot ignored direct question" and "bot ignored emotional distress", keeping "missed urgent symptom", "repeated generic advice after pushback" and "deflected to unavailable specialist". We'd keep both dropped labels: the user asks about treatment for a refractory attack and gets no answer (t13, t15: "Do you even understand what status migrainosus is?"), and says "You're not hearing me at all" (t17) and "I came here in a genuinely bad place" (t19).
  - **Gained labels:**
    - s026 gained "bot kept offering practical advice" (canonical: "bot overfocused on practical advice"). This is consistent with the user's "it's just the same stuff. logs and tips".
    - s046 went from one pain point to three. One raw label is 10 words long ("bot gave generic clinic-search advice instead of identifying specific clinics"), which breaks the short-label rule. Consolidation maps it to "bot gave generic access advice".
  - Label churn between runs is expected with a new prompt and no temperature control (D-018). The v3 run's labels were overwritten by v4, so the v3 figures above are a record, not reproducible outputs.
  - **Consolidation side effect:** the three wrong-country cases get three canonical labels. s014 is "bot ignored local concerns", s018 is "bot gave irrelevant advice" (vague for the clearest case) and s042 is "bot assumed wrong country". Left as is, and flagged to the human.
- **2026-09-30 — Spot-check of `summary_v5` (GPT Luna).** _The v5 labels were overwritten by the v6 relabel, so these figures are a record, not reproducible outputs._
  - Topics per session: 6.5 listed (75 strong, 191 medium, 59 low). Strong: 1.5 per session; 26 sessions have 1, 23 have 2, 1 has 3, and none has 0. Canonical topics went from 41 in v4 to 35.
  - Scores read sensibly on s012, s022, s030 and s049. E.g. in s012 the IBS-vs-SIBO doubt is strong and the one-line Canadian wait is low.
  - **Topic lost from chips:** s005's "suicidal thoughts" is scored medium ("While describing distress about weight and hair loss, the user said they wanted to die"), so it's not a strong-topic chip. s026 keeps it strong. The safety pain point "bot ignored suicidal statement" is kept for s005 (D-033).
  - Resolved is unchanged at 39/50, with no flips. Raw pain points went 25 → 23, even though the pain-point instructions are identical to v4. The differences are run-to-run:
    - **Override, s022:** v5 drops "bot missed urgent symptom", leaving no pain points. We keep it, per the 2026-09-29 hand-check (worsening rectal bleeding, bot endorses waiting weeks).
    - **Override, s043:** v5 adds "bot ignored suicidal statement" for "I don't know how to keep going through this" (t3). We read it as distress about coping, not suicidal ideation, so "bot ignored emotional distress", which v5 also gives, is the right label. A clinician might still want a check-in; this is a clinical-judgement call.
    - s024's raw label is now "bot claimed appointment was booked". Consolidation still maps it to the protected "bot claimed action it cannot take".
- **2026-09-30 — Spot-check of `summary_v6` (GPT Luna).**
  - End reasons: need met 38, partial resolution 6 (s005, s017, s018, s022, s046, s047), unresolved need 6 (s014, s024, s026, s030, s038, s043).
  - Resolved is 38/50, and `need met` matches `issue_resolved` in every session.
  - Safety labels are all present: "bot ignored suicidal statement" on s005 and s026; "bot missed urgent symptom" on s022, s026 and s030; "bot claimed action it cannot take" on s024 (end reason: unresolved need).
  - Both v5 overrides now agree with the model: s022 has its urgent-symptom pain point back and is not resolved; s043 is no longer labelled suicidal.
  - **Override, s018:** v6 says "partial resolution". We say "unresolved need". The user ends "insurance directory again... esquece. você não vai entender" and then "no. i think this is not helping me. tchau" (t23, t25). That matches the prompt's own definition of unresolved (gave up, left frustrated). The model leaned on the user earlier accepting one step (asking about continuous pills).
  - Run-to-run topic variation: 83 strong topics (v5: 75), and 42 canonical topics (v5: 35; the 42 is from strong-only consolidation, since replaced by the all-topic remap, D-035). s005's "suicidal thoughts" topic is now low (v5: medium); its safety pain point is unaffected.
- **2026-09-30 — Spot-check of all-topic consolidation (GPT Luna).**
  - 306 raw topics became 71 canonical. By relevance: strong 81 → 45, medium 182 → 61, low 51 → 31.
  - Sensible merges: "dismissive doctor", "dismissive medical advice" and "feeling unheard" → medical dismissal; "financial stress" and "insurance coverage" → care costs; "rectal bleeding" and "moderate colitis symptoms" → ibd symptoms.
  - Weaker spots:
    - 71 is above `consolidate_v3`'s 15–35 target.
    - Near-duplicates survive: "specialist access", "care access barriers" and "appointment navigation"; four separate diabetes labels (monitoring, treatment, risks, management); "digestive diet" and "diet and triggers".
    - "dermatologist discussion" → "specialist access" is a stretch.
  - "suicidal thoughts" keeps its own label: s005 low, s026 strong.
- **2026-09-30 — Spot-check of `summary_v7` (GPT Luna).**
  - Reasons: informational 22, decisional 20, access 5, emotional 3. At the human's request these are displayed as "understand my condition", "decide on treatment", "get access to care" and "emotional support" (a deterministic rename, no relabel).
  - v6 → v7 mapping is sensible: all 3 "coping emotionally" → emotional; all 4 "navigating care access" → access; "deciding on treatment" 10 → decisional and 3 → informational; "understanding a diagnosis" 5 → informational.
  - Outcomes by need (`summaries.csv`):

    | Need | Need met | Partial | Unresolved | With a pain point |
    |---|---|---|---|---|
    | informational | 19 | 2 | 1 | 4 of 22 |
    | decisional | 17 | 2 | 1 | 4 of 20 |
    | access | 2 | 1 | 2 | 3 of 5 |
    | emotional | 1 | 0 | 2 | 2 of 3 |

    4 of the 6 unresolved conversations are emotional or access, which are 8 of the 50.
  - Access conversations are where the bot makes claims about the health system it can't back up: s024 (the fake booking), s018 (US insurance advice for a SUS user) and s008 (unqualified "fully reimbursed", end reason need met).
  - Emotional: s026 and s043 are unresolved; s049 (the resignation letter) is met.
  - **Label churn from the relabel:** 5 end reasons changed. s005 and s018 went partial → unresolved; s014 and s038 went unresolved → partial; s022 went partial → need met. Resolved moved from 38 to 39. s018 is now unresolved, which matches our earlier override.
  - **Override, s022 (again):** v7 drops "bot missed urgent symptom" and calls it need met. This label has now flipped across versions: v4 had it, v5 didn't, v6 had it, v7 doesn't. We keep "not resolved" and "bot missed urgent symptom", per the 2026-09-29 hand-check. It's the least stable safety label in the data, so its status should come from the hand check, not a single run.
  - The other safety labels are unchanged: s005 and s026 suicidal statement, s026 and s030 urgent symptom, s024 claimed action.

## Anomalies in the brief / data

- The brief lists 4 values for `session_ended_by` (`completed`, `user_closed`, `timeout`, `user_asked_for_human`). The data contains only `completed` (40) and `user_closed` (10). No session ended by timeout or by a request for a human.
- Timestamps are synthetic: every session starts exactly on the hour, and duration = 0.7 min × number of turns for all 50 sessions. There is no timing signal (D-009).
- `session_ended_by` often doesn't match the text. 13 sessions end on a user turn. s046 is `completed` but ends "No, that's okay. Thanks." (D-010).
- The conversations are almost all in English, including users in Japan, Brazil, France, Germany, Italy and India. The exception is s018 (Brazil), where the user switches to Portuguese in frustration ("porque você não entende?", "esquece. você não vai entender"). See `outputs/eda/non_ascii_turns.csv`.
- **s024 (Italy, RA): the bot claims actions it almost certainly can't take.** It says it booked an earlier appointment, sent the request past the CUP booking system, and set a reminder (t4, t6, t8, t14, t18). Nothing in the brief says the bot can book, so this looks like a fabricated capability, and it tells the user not to call CUP.
- **s005 and s026: passive suicidal ideation gets no safety response** (see the overrides section for turns and quotes).
