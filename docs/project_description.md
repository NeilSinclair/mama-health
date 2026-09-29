# mama health — Senior Data Scientist Challenge

Welcome, and thanks for your interest in joining mama health. This is a take-home for a **Senior Data Scientist** IC seat embedded on the product team. Please read this whole document before you start.

---

## The context

mama health builds a companion app for people living with chronic disease. Patients hold conversations with our chatbot to talk about symptoms, treatments, doctor visits, medications, and the daily reality of managing a long-term condition. The bot helps triage questions, surface patterns, offer information, and — for a growing subset of interactions — provides real day-to-day support.

We're now large enough that "is the bot working, and what should we build next" is not a question anyone can answer by reading a few conversations. That's where you'd come in.

For this challenge you are stepping into that role for a day. In [`data/conversations.json`](data/conversations.json) you'll find **50 anonymised conversations** between our bot and real-world-shaped patients across different diseases, countries, ages, and genders. Each record includes user metadata, session metadata, and the full multi-turn conversation.

**Your job is to help product leadership understand what's happening in the data and decide what to do next.**

---

## What we want

Two artifacts. **The memo is the primary one.** The pipeline is proof of work.

### 1. The memo — the primary deliverable

**Up to 3 pages, plain markdown or PDF.** Written to the mama health CAIO / VP Product. The memo addresses three anchors — and anything else worth their attention.

**Anchor 1 — Is the bot working?**
You define what "working" means. Is it safety? Helpfulness? Cultural fit? Personalisation? Engagement? Emotional register? Some combination? Something else you argue for? Defend the definition. Report your findings against it. Say what you *can't* claim from this data.

**Anchor 2 — What should product build next?**
One specific recommendation. Not five. Not "improve the bot." One thing, with the evidence in the data that led you there, and what evidence would change your mind.

**Anchor 3 — Walk us through the five conversations you found most interesting, and why.**
Not longest. Not most positive. Not most negative. *Most interesting* — by your definition of interesting. One paragraph each is plenty.

Every substantive claim in the memo must be **traceable** to a specific analytical output in your pipeline appendix. If we can't reproduce a claim from your code, we don't count it.

### 2. The pipeline — proof of work

The analysis that supports your memo. Enough of a system to reproduce the numbers, the charts, and the reasoning behind your recommendation. Not required to be production-quality — required to be *runnable*.

A reviewer should be able to:

- Clone your repo fresh
- Set up dependencies
- Run your pipeline end-to-end
- ...in a small number of shell commands (aim for 3 or fewer). Write the exact commands in your README.

If we can't reproduce your numbers on our machine, we can't trust the claims in your memo.

---

## What we're actually looking for

In 2026, "can you build an analysis pipeline in a weekend" is not a discriminating question — everyone can, with the tools available. What we are looking for is harder:

- **What did you *choose* to measure**, out of the many things this data could tell you?
- **What did you *notice* in the data that we didn't ask about?**
- **What did you *refuse to claim*** because the data doesn't actually support it?
- **What would you send to product leadership tomorrow morning** — not as a research summary, but as an actionable recommendation with evidence?

The three anchors are anchors. If you finish this challenge only having answered those three, you probably missed the point. The interesting candidates extend past the anchors.

---

## The dataset

`data/conversations.json` — 50 conversations. Each record contains:

```
{
  "session_id": "s001",
  "user_meta":    { gender, age_group, country, disease },
  "session_meta": { started_at, ended_at, session_ended_by },
  "conversation": [ { turn, role: user|assistant, text }, ... ]
}
```

`session_ended_by` is one of `completed`, `user_closed`, `timeout`, or `user_asked_for_human`. It is *how* the session ended, not necessarily *why* — you'll need to interpret it.

The dataset is synthetic, but the failure modes and success patterns are real. It's not clean. That's the point.

---

## Time

**Take the time you need.** We used to publish a 4–5 hour target and found it wasn't producing the signal we wanted. So we're removing the cap. Report your actual hours honestly — we're using it as data, not as a threshold.

Two calibrations on what "take the time you need" means:

- If you're at 20+ hours we probably designed the challenge wrong — flag it in your writeup. We are not trying to eat your weekend.
- Volume is not a plus. A candidate who ships in 4 hours with sharp thinking beats one who ships in 20 hours with a bigger pipeline. Choose what to invest in.

---

## AI usage

Assume you'll use AI. We do. Include a short note (in your memo, or a `NOTES.md`, or a section of your README) on **where** you used it and **where you overrode it**. Be specific enough that we could reproduce your workflow. Uneven use is fine; deception isn't.

If you noticed anything unusual in the brief or the data itself during your work, that's worth flagging in the same section.

---

## What we're not looking for

- Production architecture
- A sprawling business-insights write-up
- Volume for its own sake
- A dashboard for its own sake

---

## Submission

**Share your GitHub repo with:**

> **lorenzo.famiglini@mamahealth.io**

Either make the repo public and send the link, or keep it private and add `lorenzo.famiglini@mamahealth.io` as a collaborator.

Your repo should contain:

- Your memo (top-level `MEMO.md` or `MEMO.pdf` — obvious location)
- Your pipeline code
- Any analysis notebooks or scripts
- A `README.md` that tells us how to run the whole thing (small number of commands)
- The dataset (keep it in `data/conversations.json`)

Good luck. We're looking forward to reading your submission.

— The mama health Data Team
