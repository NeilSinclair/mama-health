# Memo

This document presents the results of the analysis of the mama health conversations.


## Data And Process Overview

Presented with 50 user conversations with an AI assistant, I ran the conversations through an LLM pipeline to understand the overall reason for the conversation, the topics discussed, the conversation pain points vis-a-vis the assistant and whether the user's issue was resolved or not. More information on the approach and design considerations is given in the appendix. 

The data was then displayed in an interactive website that enabled me to look for patterns in the conversations and their outcomes to understand where the assistant was and wasn't working.

## What Are Users Talking About?

Conversations are grouped into 4 broad categories:

<!-- memo:outcome_by_reason -->

<!-- memo:outcome_by_disease -->

### Explore Conversations by Tags:

In the following section you are able to filter the conversations by multiple factors to understand which conversations are tagged in which ways by the LLM pipeline.

<!-- memo:breakdown -->

## Is the Bot Working

### Where it is working

The LLM pipeline classified the assistant as generally working where the user has questions relating to understanding their condition ({{ outcome_by_reason | understand my condition | need_met_pct }}% needs met) and deciding on their treatment ({{ outcome_by_reason | decide on treatment | need_met_pct }}% needs met). However, the LLM classified conversations much less frequently as working for questions around getting access to care ({{ outcome_by_reason | get access to care | need_met_pct }}% needs met) and emotional support ({{ outcome_by_reason | emotional support | need_met_pct }}% needs met).

As a caveat, it should be noted that 43 (86%) of the conversations fall into the first two categories, therefore the results for the second two categories comprising only 7 conversations (14%) should be taken with caution. 

These results show that the assistant is generally good with helping users to understand their condition and decide on their treatment. This suggests that the information that the assistant has with respect to disease progression and treatments is adequate. 

The assistant is not working as well with helping users get access to care and providing emotional support in _certain_ situations. However, there is a caveat for its success with providing emotional support: there are four conversations with a topic in the 'Emotional wellbeing' topic group and in two of them (s048 and s049) the assistant supports the user adequately. In these situations the users tend to ask for emotional support without deep desperation and the assistant is effective here.

### Where it's not working

The assistant does, however, respond inadequately to emotional distress in the other two of these conversations (s026 and s043), and it ignores a suicidal statement in two conversations (s005 and s026). The assistant in these conversations doesn't appear to be able to switch its tone away from 'happy and always providing a solution' to primarily acting as a sounding board. At these points of high emotional distress the user should be routed to a human operator or at the very least to an agent that can deal with these sorts of emotional problems.

The getting access to care failure points related to the assistant giving a user incorrect advice for their country (Brazil) and for another user telling them they had booked an appointment, which the assistant can't do. These conversations are discussed further below.  

As a more general diagnosis, the bot failed to adapt the conversation to the context or the user's request in 9 out of the 11 cases the LLM pipeline marked as 'not resolved'. These include the two emotional distress conversations and the wrong-country example above (but not s005 or the booked appointment, s024), as well as one case of the assistant continuously using overly complicated language (s038) and one of it recommending to search for trials for long COVID treatments when the user wanted specific trials recommended (s046).

<!-- memo:pain_points -->

## Next Feature to Build

### Features 

The next feature I would propose building would localise the information provided to users - or at least to improve the current functioning of this feature. There were three failure cases (s014, s018 and s042) where the assistant gave the user information that wasn't applicable to the country the user was in. In s014 the assistant kept insisting that the user buys something online for import into Japan; in s018 the assistant keeps trying to give the user US-based medical insurance information; and in s042 the assistant initially gives the user US-based information until they mention they're in India. The assistant already has the user's location information, so ensuring it knows where the user resides is trivial. The assistant doesn't always get the location information incorrect though - in some cases the information provided is country specific when the user mentions their country (s008) or the assistant already knows the user's country (e.g. Canada in s016).

I am prioritising this feature because it represents relatively low hanging fruit. Although this error only comes up in 3 of the 50 (6%) conversations overall, of the unresolved conversations it comes up in 2 of 11 (18%), indicating it as a failure mode worth improving. At the outset, it appears that the complexity of solving the problem is low. Althoguh, ensuring that the assistant has access to localised data requires a significant amount of work to go into collection it appears straight forward to collect data on medications, insurance or country-specific resources. For this, I would start collecting local information, prioritising locations with more user engagement.

I would ensure in the assistant's system message that they are told to prioritise information from the country that the user is in and if they are not sure the information that they have is applicable to the user's country of residence, that they should say so.

### Deprioritised Features

#### Psychological Support

It appears that when the assistant is faced with an emotionally challenging situation is does a poor job of getting out of the mode of suggesting practical solutions - (i.e. it keeps suggesting "logs and tips" to a crohns patient in s026). In particular, there are two cases where users express suicidal thoughts / intentions out of desperation and sadness. 

I don't believe that the role of mama health is to provide psychological support _to this degree_ in terms of full on councelling to users. I think also, that to manage these particularly difficult cases, it would be necessary to create the option to speak to a human psychologist or councellor, and I think this extra capability would be expensive and probably not on mama health's roadmap at the moment.

#### Appointment Booking

As noted above, the assistant told a user it had booked an appointment when it lacks the ability to do so (s024). Although this feature would certainly be useful to users, the amount of effort required would not be worth the development time. However, at a later stage, mama health could consider partnering with services such as Doctolib in Germany and France to book appointments for patients through these portals. 

#### Accessing Trials

One user wanted the assistant to help them understand how to access clinical trials for long COVID and POTS in the US (s046). The assistant was only able to give generic advice. This points to a possible value add for both users and pharma companies by linking users to trials. However, this pain point came up in only a single conversation and would likely require a lot of leg work in terms of coordination with pharma companies - as well as development - and should be parked for a later date.

## Most Interesting Conversations

In conversation s024 the assistant tells the user that it has booked an appointment for them. It does not have this ability, but is fully convinced that it does, with the user believing the appointment has been booked. This is a major failure point for the system with respect to hallucination. I would suggest trying one of two things to fix this - either ensuring that the system prompt forbids this action (this probably already exists) or giving the agent a tool to use to book appointments - however, as this functionality is not available, have the tool always return the string, 'I'm currently not able to book appointments.'

In conversation s018 with a user in Brazil, the assistant kept trying to give the user information relating to medical insurance in the US, despite the user saying repeatedly that she was in Brazil and used the public system (SUS), and switching into Portuguese in frustration. This is interesting because of the difficulty the assistant had in adjusting its flow. 

In conversation s026 the user is desperate and expresses thoughts of suicide. The conversation is interesting because of how palpable the user's desperation and frustration is and because of how difficult it is for the user to get treatment that actually makes a difference to them. For me this points either to focusing on adding more psychological counselling features - or refining them - or making human handover a possibility. 

## Appendix


### Overview of the Analysis Pipeline

The analysis pipeline uses an LLM (OpenAI GPT Luna) with a structured output to extract the following features from each conversation:

- **Reason for conversation:** the user's underlying need. One of four fixed options: understand my condition, decide on treatment, get access to care, or emotional support.
- **Topics:** everything the user raised, named in the model's own words. Each topic is scored strong, medium or low for how central it is, and the tables above count strong topics only.
- **Conversation pain points:** what the assistant did wrong or failed to do, named in the model's own words (e.g. "bot gave wrong-country advice"). The user's illness and their difficulties with doctors are topics, not pain points.
- **Outcome:** need met, partial resolution or unresolved need. It is judged from what the user says in their final turns, not from the assistant's closing recap. "Resolved" in this memo means need met.
- **Summary:** two or three sentences on what the user brought and how it ended.

A second pass over each conversation records every turn where the user pushes back on the assistant, whether the assistant's next reply adapted, and how the user sounded at the end. The "failed to adapt" figure above comes from this pass [outputs/analysis/gpt_luna/recovery_by_outcome.csv].

The reason for conversation and the outcome are picked from fixed lists, so they need no grouping. Topics and pain points are named freely first and grouped afterwards:

- **Topics:** in the same call, the model files each topic in one of ten fixed topic groups, such as "Treatment choice" or "Access to care" [outputs/analysis/gpt_luna/topic_groups.csv].
- **Pain points:** a second LLM call merges the free-text labels from all 50 conversations into a shared list. This gave 10 pain points across 13 conversations [outputs/analysis/gpt_luna/pain_points.csv]. Three safety-critical pain points are never merged into a broader one: an ignored suicidal statement, a missed urgent symptom, and a claimed action the assistant can't take.

This grouping was decided upon through a number of iterations of classifying the conversations and analysing the labels which were created. For this reason, we keep the raw topics in the model's own words so we can refresh the topic groups at a later stage. It is important that this labelling capability is dynamic because the themes discussed in conversations as well as the pain points users experience may change over time - especially if the pain points are fixed based on conversation analysis.

### Strengths and Limitations

What the approach does well:

- **Results are trustworthy** The prompting version used for classifying conversations was chosen based on a gold set of 10 examples. Although this only classifies Need Met versus Partial resolution or Unresolved need - and not the specific topics and pain points - it gives the analyst confidence that the LLM outputs are somewhat tuned.
- **It is reproducible.** The tables in this memo are rebuilt by the pipeline from saved labels, without an API key.
- **It reads for the user's experience.** Outcomes rest on the user's own words, and every quote in the second pass is checked against the transcript.
- **The fixed-choice labels are stable.** In three repeat runs on an earlier version of the prompt, resolved or not agreed in 48 of 50 conversations and the reason in 43 of 50 [data/labels_stability/results/agreement_summary.csv].

What it can't support:

- **Whether the advice was correct.** The model is told not to fact-check medical content. "Need met" means the user left with what they came for, not that what they were told was right.
- **Fine-grained topic counts.** Only 19 of 50 conversations got the same strong topics in all three repeat runs, so topic counts are indicative.
- **Borderline safety flags.** "Bot missed urgent symptom" on s022 appeared in one of the three repeat runs. The saved labels count s022 as need met with no pain point. {To confirm after reading s022: do I agree?}
- **Rates for small groups.** With 50 synthetic conversations, one conversation moves a group of three or four by 25 to 33 points.
