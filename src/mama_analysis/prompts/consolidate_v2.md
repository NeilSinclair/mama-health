You are consolidating free-text labels produced by an earlier pass over 50 chatbot conversations between a health-companion bot and people with chronic disease. Each conversation was labelled independently, so the raw labels are specific, one-off phrasings ("CGRP inhibitors", "TSH creep on stable dose", "four-day migraine unresponsive to triptans"). Your job is to map every raw label to a **category** a product manager would filter on in a UI, so the labels can be counted and compared across conversations.

The raw label stays visible in the UI next to its category, so nothing is lost by mapping a specific label to a broader one. A filter whose every option matches one conversation is useless. In a previous run nearly every label was mapped to itself; do not do that.

The user message names the field (`main_topics`, `pain_points`, `reason_for_conversation` or `end_reason`) and lists every unique raw label, one per line. Return a list of pairs, one per raw label: `raw` (the label exactly as given) and `canonical` (the category it belongs to). The output format is enforced; this prompt explains how to decide.

## Hard requirements

- Every raw label appears exactly once in the output, copied verbatim: same spelling, casing, punctuation, typos and whitespace. Never add, drop, trim or correct a raw label.
- Canonical labels are lower-case English noun phrases of 1 to 4 words, with no session-specific details (no names, doses, numbers, dates, places, drug brand names). Exception: bot pain points, which stay short phrases starting with "bot" (see below).
- One spelling per category. Every raw label in the same category must have a byte-identical `canonical` string.
- The vocabulary for a field should read as one list: same grammatical form, same level of generality throughout.

## Target size

Aim for **10 to 30 categories** for `main_topics` and `pain_points`, and fewer (roughly 6 to 15) for `reason_for_conversation` and `end_reason`, whose natural vocabularies are small. These are targets, not hard limits, but finishing well outside them means your level of generality is wrong.

A category covering a single raw label should be rare. Keep a singleton only when the label is genuinely unlike everything else, not merely more specific than its neighbours. A drug name, lab value, procedure or body part is almost never a category on its own; it is an instance of one.

## Level of generality

Pick the level a product manager would use to ask "how many conversations were about X?". Concretely:

- Drugs and drug classes map to what they are *for* or what is being asked about them: "CGRP inhibitors", "migraine preventative medications" and "comparison of preventative options" all belong to something like `preventive medication`; "levothyroxine dose adjustment", "mesalamine dosing" and "dose adjustment and timing" to `medication dosing`.
- Individual lab values and test results map to the activity: "TSH creep on stable dose", "A1C rise without lifestyle change", "interpreting clinical benchmarks" belong to something like `lab results interpretation`.
- Disease-specific phrasings map to the generic concern: "colorectal cancer risk in ulcerative colitis", "cancer risk and family history" both belong to `cancer risk`; "long waits for gastroenterology appointments", "neurologist unavailable for six weeks", "long dermatology wait times" all belong to `specialist wait times`.
- Needs map to need types, not to the disease or drug mentioned: "decide whether to start a biologic treatment" and "deciding whether to delay medication in favour of lifestyle changes" are both `deciding on a treatment`.

Do not go one level higher than this. Categories that would match most conversations (`symptoms`, `treatment`, `health`, `medication`, `emotional support`, `worry`) are forbidden. If you find yourself writing one, split it by what the conversation is actually *about*: side effects vs dosing vs cost vs safety in pregnancy are different categories even though all are "medication".

Do not merge genuinely different things just to hit the target: `medication side effects` and `medication cost` stay apart; `specialist wait times` and `dismissive doctor` stay apart; `need met` and `user accepted partial answer` are different outcomes.

## Working method

1. **Draft the category list first.** Read the whole input, then decide the categories the field needs, at the level described above, before assigning anything.
2. **Assign every raw label** to one category from the list. If a label fits nothing, either add a category (and check whether other labels now belong there too) or, rarely, keep it as a singleton.
3. **Check counts.** Count raw labels per category. Merge categories a product manager would not tell apart; split any that has absorbed most of the list; confirm singletons are truly one of a kind.
4. Give each category its final name: the plainest term a product team would recognise on sight.

## Field-specific guidance

- `main_topics`: categories are subjects at the level of `preventive medication`, `medication side effects`, `diet and triggers`, `fatigue and pacing`, `sleep`, `fertility and pregnancy`, `work and employment`, `emotional impact`, `accessing specialist care`, `new diagnosis basics`, `cancer risk`, `lab results interpretation`. Keep a treatment topic separate from its side effects, and a symptom separate from the decision about it.
- `pain_points`: two families that must never share a category. Labels starting with "bot" describe something the bot did or failed to do; they keep a "bot" prefix and merge only with other bot labels. Everything else describes hardship from the condition or the health system and merges only with each other. Within the bot family, merge variants of the same failure mode (every "repeated advice despite pushback" phrasing is one category) but keep failure modes apart when they point to different fixes: ignoring emotional content, repeating advice, deflecting to a doctor or to logistics, wrong-country assumptions, contradicting itself or giving wrong facts, missing urgency, not simplifying language. A "no bot pain" marker, if present, is its own category.
- `reason_for_conversation`: categories are need types such as `understanding a new diagnosis`, `deciding on a treatment`, `understanding a medication`, `managing side effects`, `understanding a symptom or result`, `coping emotionally / wanting to be heard`, `navigating access to care`, `urgent symptom help`, `planning around life events`. A raw label that names two needs goes to the dominant one (the one the user actually wanted resolved).
- `end_reason`: categories name why the conversation stopped. Keep resolved endings (need met) apart from partial resolution and from unresolved ones (gave up, left unheard). This vocabulary is usually already small; merge only true wording variants.

## Before answering

- Output pairs equal the number of input lines, each raw verbatim.
- Category count is near the target for this field; singletons are rare and justified.
- Every category has exactly one spelling.
- No bot pain shares a category with a condition or care pain.
- No category is a catch-all that would match most conversations.
