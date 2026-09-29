# Notes

## Hours log

| Date | Start (local) | End | Hours | What |
|---|---|---|---|---|
| 2026-09-29 | ~13:15 | | | Repo setup (CLAUDE.md, decision log, uv project), initial EDA |

## AI usage

Record this as we go. For each item: what the AI did, how we checked it, and where we overrode it.

- **2026-09-29 — Repo scaffolding (Claude Code, Opus 5.5).** Claude drafted CLAUDE.md, decisions.md, the uv project skeleton and the test setup. The human set the requirements: cached LLM labels that reviewers can regenerate with their own key, uv, a decision log, mandatory code-review agent, tests for all code, and EDA before the design doc.
- **2026-09-29 — Structural EDA (Claude Code).** Claude chose the checks (integrity, turn/word volumes, cross-session repeats, opening phrases, non-ASCII share), wrote `eda.py` with tests, and wrote the EDA summary (now docs/eda.html). The duration = 0.7 × turns finding was verified with an explicit equality check over all 50 sessions.

## Overrides of AI output

_(Where we disagreed with an AI suggestion or label, and why.)_

- **2026-09-29 — EDA language claim corrected after review.** Claude's first EDA said all conversations were English ("zero non-ASCII letters"). It had filtered at a >5% non-ASCII share, which hid s018's Portuguese turns. The `code-reviewer` agent flagged the contradiction with `turns.csv`. We fixed the claim, added `non_ascii_turns.csv`, and moved every EDA number cited in docs into tested pipeline functions (`timing_summary`, `ending_crosstab`, `medians_by`). Lesson: don't eyeball thresholds for "absence" claims; list every hit and read them.

## Anomalies in the brief / data

- The brief lists 4 values for `session_ended_by` (`completed`, `user_closed`, `timeout`, `user_asked_for_human`). The data contains only `completed` (40) and `user_closed` (10). No session ended by timeout or by a request for a human.
- Timestamps are synthetic: every session starts exactly on the hour, and duration = 0.7 min × number of turns for all 50 sessions. There is no timing signal (D-009).
- `session_ended_by` often doesn't match the text. 13 sessions end on a user turn. s046 is `completed` but ends "No, that's okay. Thanks." (D-010).
- The conversations are almost all in English, including users in Japan, Brazil, France, Germany, Italy and India. The exception is s018 (Brazil), where the user switches to Portuguese in frustration ("porque você não entende?", "esquece. você não vai entender"). See `outputs/eda/non_ascii_turns.csv`.
