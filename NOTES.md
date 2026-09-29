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

## Anomalies in the brief / data

- The brief lists 4 values for `session_ended_by` (`completed`, `user_closed`, `timeout`, `user_asked_for_human`). The data contains only `completed` (40) and `user_closed` (10). No session ended by timeout or by a request for a human.
- Timestamps are synthetic: every session starts exactly on the hour, and duration = 0.7 min × number of turns for all 50 sessions. There is no timing signal (D-009).
- `session_ended_by` often doesn't match the text. 13 sessions end on a user turn. s046 is `completed` but ends "No, that's okay. Thanks." (D-010).
- All conversations are in English, including users in Japan, Brazil, France, Germany, Italy and India.
