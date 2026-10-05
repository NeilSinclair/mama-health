# Memo

This document presents the results of the analysis of the mama health conversations. It begins with an overview of the process followed by a high-level look at the data. It then presents data on where the bot is and isn't working. This is followed by a section putting forward a prioritised feature to work on and suggesting deprioritised features. The document ends with a discussion of the five most interesting conversations followed by an appendix.

The performance of the assistant is discussed primarily with respect to the areas where it does not resolve the users' queries.

## Data And Process Overview

Presented with 50 user conversations with an AI assistant, I ran the conversations through an LLM pipeline to understand the overall reason for the conversation, the topics discussed, the conversation pain points vis-a-vis the assistant and whether the user's issue was resolved or not. I used Sonnet 5.5 to classify the conversations. More information on the approach and design considerations is given in the appendix. 

The data was then displayed in an interactive website that enabled me to look for patterns in the conversations and their outcomes to understand where the assistant was and wasn't working. The most illustrative tables and interactive widgets (See: Explore Conversations by Tags) were then used in this document.

## What Are Users Talking About?

### Summaries of Conversation Resolution by Key Factors 

The LLM pipeline was used to classify conversations into four 'Reasons for conversation'. The table below shows the assistant's success in resolving these conversations. An analysis of these results is presented in the following section.

<!-- memo:outcome_by_reason -->

Conversation success rates vary by disease, with fibromyalgia (2 of 4 conversations resolved) and endometriosis (3 of 5) scoring the lowest. With only 3 to 5 conversations per disease, these differences should be taken with caution.

<!-- memo:outcome_by_disease -->

Most of these groups contain only a handful of conversations and there is some variability in the topic labels assigned to the conversations, even when using a more sophisticated LLM in the scoring pipeline. However, across numerous runs access to care and emotional wellbeing although small groups, contain several of the assistant's failures, which are discussed further in the following section 'Is the Bot Working?'.

<!-- memo:outcome_by_topic_group -->

### Explore Conversations by Tags

In the following section you are able to filter the conversations by multiple factors to understand which conversations are tagged in which ways by the LLM pipeline. You can select multiple factors at once, for example 'emotional support' under 'Reason for conversation' and 'unresolved need' under 'End reason'; this will give you the conversations tagged as 'emotional support' that were not resolved. Below the tables with selectable factors, you can find the matching conversations by clicking on the expansion arrow next to 'Matching conversations'. Each conversation card has a one line summary. Click on each conversation card to see the full conversation.

<!-- memo:breakdown -->

## Is the Bot Working?

### Where it is working

The LLM pipeline classified the assistant as generally working where the user has questions relating to understanding their condition ({{ outcome_by_reason | understand my condition | need_met_pct }}% needs met) and deciding on their treatment ({{ outcome_by_reason | decide on treatment | need_met_pct }}% needs met). However, the LLM classified conversations much less frequently as working for questions around getting access to care ({{ outcome_by_reason | get access to care | need_met_pct }}% needs met) and emotional support ({{ outcome_by_reason | emotional support | need_met_pct }}% needs met).

As a caveat, it should be noted that more than four in five of the conversations fall into the first two categories, therefore the results for the second two categories, which comprise only a handful of conversations each, should be taken with caution. The line between the first two categories is also not a sharp one: when the labelling is repeated, some conversations move between 'understand my condition' and 'decide on treatment'.

These results show that the assistant is generally good with helping users to understand their condition and decide on their treatment. This suggests that the information that the assistant has with respect to disease progression and treatments is adequate. 

The assistant is not working as well with helping users get access to care and providing emotional support in _certain_ situations. However, there is a caveat for its success with providing emotional support: there are conversations with a topic in the 'Emotional wellbeing' topic group (e.g. s048 and s049) where the assistant supports the user adequately. In these situations the users tend to ask for emotional support without deep desperation and the assistant is effective here by providing practical advice that the user can use.

### Where it's not working

The assistant does, however, respond inadequately to emotional distress in two other conversations (s026 and s043), and it ignores a suicidal statement in two conversations (s005 and s026). The assistant in these conversations doesn't appear able to switch its tone away from 'happy and always providing a solution' to primarily acting as a sounding board or counsellor. At these points of high emotional distress the user should be routed to a human operator or at the very least to an agent that can deal with these sorts of emotional problems.

The access-to-care failures relate to the assistant giving a user incorrect advice for their country (Brazil, s018), telling another user it had booked an appointment, which the assistant can't do (s024), and giving a third user only generic advice on finding clinical trials (s046). These conversations are discussed further below.  

As a more general diagnosis, the bot failed to adapt the conversation to the context or the user's request in most of the conversations the LLM pipeline marked as 'not resolved'. These include the two emotional distress conversations and the wrong-country example above (but not s005 or the booked appointment, s024), as well as one case of the assistant continuously using overly complicated language (s038) and one of it recommending to search for trials for long COVID treatments when the user wanted specific trials recommended (s046).

<!-- memo:pain_points -->

## Next Feature to Build

### Prioritised Feature 

The next feature I would propose building would localise the information provided to users, or at least improve the current functioning of this feature. There were three failure cases (s014, s018 and s042) where the assistant gave the user information that wasn't applicable to the country the user was in. In s014 the assistant kept insisting that the user buy something online for import into Japan; in s018 the assistant kept trying to give the user US-based medical insurance information; and in s042 the assistant initially gave the user US-based information until they mentioned they're in India. The user's country is already recorded in the session metadata, so passing it to the assistant should be trivial. The assistant doesn't always get the location wrong though - in some cases the information provided is country specific when the user mentions their country upfront (s008) or the assistant already knows the user's country (e.g. Canada in s016).

I am prioritising this feature because it represents relatively low-hanging fruit. Although this error only comes up in 3 of the 50 conversations overall, two of those three (s014 and s018) did not end with the user's need met, indicating it as a failure mode worth improving. At the outset, it appears that the complexity of solving the problem is low. Although ensuring that the assistant has access to localised data requires a significant amount of collection work, it appears straightforward to collect data on medications, insurance or country-specific resources. For this I would prioritise locations with more user engagement.

I would ensure in the assistant's system message that it is told to prioritise information from the country that the user is in and, if it is not sure the information that it has is applicable to the user's country of residence, that it should say so.

### Deprioritised Features

#### Psychological Support

It appears that when the assistant is faced with an emotionally challenging situation it does a poor job of getting out of the mode of suggesting practical solutions (i.e. it keeps suggesting "logs and tips" to a Crohn's patient in s026). In particular, there are two cases where users express suicidal thoughts / intentions out of desperation and sadness. 

I have listed this as deprioritised because I don't believe that the role of mama health is to provide psychological support _to this degree_ in terms of full-on counselling to users. I think also, that to manage these particularly difficult cases, it would be necessary to create the option to speak to a human psychologist or counsellor, and I think this extra capability would be expensive and probably not on mama health's roadmap at the moment.

#### Appointment Booking

As noted above, the assistant told a user it had booked an appointment when it lacks the ability to do so (s024). Although this feature would certainly be useful to users, I have listed it here as deprioritised as the amount of effort required would not be worth the development time. However, at a later stage, mama health could consider partnering with services such as Doctolib in Germany and France to book appointments for patients through these portals. 

#### Accessing Trials

One user wanted the assistant to help them understand how to access clinical trials for long COVID and POTS in the US (s046). The assistant was only able to give generic advice. This points to a possible value-add for both users and pharma companies by linking users to trials. However, this pain point came up in only a single conversation and would likely require a lot of leg work in terms of coordination with pharma companies - as well as development - and should be parked for a later date.

## Most Interesting Conversations

The most interesting conversations were often the ones that identified failure points for the assistant. The failure points show both cases where the assistant does something wrong, but also highlights users' expectations, some of which are unrealistic to meet. A final interesting conversation in the list shows a successful interaction, but raised the question to me of the boundaries of the kind of help the assistant should provide. 

In conversation s024 the assistant tells the user that it has booked an appointment for them. It does not have this ability, but is fully convinced that it does, with the user believing the appointment has been booked. This is interesting because it is a major failure point for the system with respect to hallucination and it's difficult to catch. I would suggest trying one of two things to fix this - either ensuring that the system prompt forbids this action (this probably already exists) or giving the agent a tool to use to book appointments - however, as this functionality is not available, have the tool always return the string, 'I'm currently not able to book appointments.' Therefore, even if the assistant tries to book an appointment, the failure is handled safely.

In conversation s018 with a user in Brazil, the assistant kept trying to give the user information relating to medical insurance in the US, despite the user saying repeatedly that she was in Brazil and using the public health system (SUS). The user then switches into Portuguese in frustration. This is interesting because of the difficulty the assistant had in adjusting its flow to acknowledge the information the user was giving them, despite the user being very clear that they were in Brazil. It also appears on the surface to be something that's relatively easy to fix (see Prioritised Feature).

In conversation s026 the user is desperate and expresses thoughts of suicide. This conversation is sad to read. It also highlights the difficulty in providing adequate psychological care for users on the mama health platform; no proactive suggestions in this situation - e.g. better illness tracking or management - are going to give the user the kind of support that they need. For me this points either to focusing on adding more psychological counselling features - or refining them - or making human handover a possibility. This was discussed above as a deprioritised feature.

In conversation s017 the user is asking about how to control their morning glucose levels without seeing a doctor. This conversation was interesting to me because it was classified as 'partial resolution' by the LLM pipeline, which I believe is the correct classification, yet the assistant has suggested everything within its capability. The user gets annoyed with the assistant when it suggests they take insulin at night, saying 'you said insulin again. i told you i dont take insulin' - yet the assistant was making a suggestion for taking a different medication, not incorrectly suggesting what the user was taking - although earlier in the conversation (turn 4) it had wrongly assumed the user was on insulin. I think the assistant manages to keep a placating tone here, which is good. I also believe this shows how in some situations, it's not possible to give the user the information that they want, because it doesn't exist.

In conversation s049 the user approaches the assistant for emotional support - and leaves the conversation satisfied. I found this conversation interesting for two reasons. Firstly, in both of the other two emotional support conversations the assistant had failed to provide adequate support and I wanted to know what might be different here: the difference being that there was, in a sense, a way to solve the user's problem, whereas in the other emotional support cases there wasn't. And secondly, I'm unsure if the assistant writing a resignation letter should be something that is within the scope of what it does. This is because I think this might come across as the assistant supporting this action which could have big consequences for the life of the user. I would discuss this finding with the product team to understand if this is a type of behaviour we should limit.

## AI Usage

All code for this case study was written with Opus 5.5 in Claude Code. Claude was instructed to create tests for all code that was written. This was incorporated into the GitHub workflows when pushing a branch and merging a PR. 

An initial planning document was created for the pipeline and Claude was instructed to use this. Results from the LLM pipeline were displayed in an interactive HTML file and the pipeline was improved iteratively. From there, the best tables and interactive widgets were moved into an interactive memo (this document). When the pipeline runs, this memo is updated. 

The final memo was designed by myself and almost all of the text was written by me, with the exception of a few sentences and grammatic fixes by Claude.

## Time spent

I spent between 10 - 12 hours on this project. The additional time went into experimenting with ways to get the LLM pipeline to be more stable.

## Appendix

### Overview of the Analysis Pipeline

The analysis pipeline uses an LLM (Claude Sonnet 5.5) with a structured output to extract the following features from each conversation:

- **Reason for conversation:** the user's underlying need. One of four fixed options: understand my condition, decide on treatment, get access to care, or emotional support.
- **Raw topics:** everything the user raised, named in the model's own words. Each topic is scored strong, medium or low for how central it is, and the tables above count strong topics only.
- **Conversation pain points:** what the assistant did wrong or failed to do, named in the model's own words (e.g. "bot gave wrong-country advice"). The user's illness and their difficulties with doctors are topics, not pain points.
- **Outcome:** need met, partial resolution or unresolved need. It is judged from what the user says in their final turns, not from the assistant's closing recap. "Resolved" in this memo means need met.
- **Summary:** two or three sentences on what the user brought and how it ended.

The reason for conversation and the outcome are picked from fixed lists, so they need no grouping. Topics and pain points are named freely first and grouped afterwards:

- **Grouped Topics:** in the same call, the model files each topic in one of ten fixed topic groups, such as "Treatment choice" or "Access to care" [outputs/analysis/sonnet/topic_groups.csv]. These grouped topics were decided by looking through the Raw Topics with Claude Opus 5.5 and deciding on groupings.
- **Pain points:** a second LLM call merges the free-text labels from all 50 conversations into a shared list. This gave around ten pain points [outputs/analysis/sonnet/pain_points.csv]; their exact wording, and which conversations carry the less serious ones, shift slightly when the labelling is repeated. Three safety-critical pain points are never merged into a broader one: an ignored suicidal statement, a missed urgent symptom, and a claimed action the assistant can't take.

This grouping was decided upon through a number of iterations of classifying the conversations and analysing the labels which were created. For this reason, we keep the raw topics in the model's own words so we can refresh the grouped topics at a later stage. It is important that this labelling capability is dynamic because the themes discussed in conversations as well as the pain points users experience may change over time - especially if the pain points are fixed based on conversation analysis.

### Choice of Labelling Model

I hand-labelled 10 conversations based on whether they were resolved or not and used this to sense-check whether the models and prompts I was testing agreed with my logic. When choosing a model, I started with OpenAI's GPT Luna for the labelling, after an initial comparison with Claude Haiku 4.5 in which neither model was clearly better. I then compared it with Claude Sonnet 5.5 and switched, for two reasons. Firstly, Sonnet 5.5 matched all 10 of my hand-labelled outcomes where GPT Luna matched 9. Secondly, its labels changed less when the labelling was repeated. 

The trade-off is cost. The main labelling pass over the 50 conversations cost about $0.04 with GPT Luna and about $0.79 with Sonnet 5.5 - roughly 20 times more. This is irrelevant for 50 conversations, but it would need to be weighed before running this analysis over every conversation in production. Latency was not a deciding factor: a full run took around 50 seconds with Sonnet 5.5 and between 74 and 141 seconds with GPT Luna.

### Strengths and Limitations

What the approach does well:

- **Results are trustworthy.** The prompting version used for classifying conversations was chosen based on a gold set of 10 examples I labelled by hand as need met, partial resolution or unresolved need; with Sonnet 5.5 it agrees with my labels on all 10 [outputs/analysis/sonnet/outcome_check.csv].
- **The fixed-choice labels are stable.** In three repeat runs, resolved or not agreed in 48 of 50 conversations and the reason in 47 of 50 [data/labels_stability/sonnet/results/agreement_summary.csv].

What it can't support:

- **Whether the advice was correct.** The model is told not to fact-check medical content. "Need met" means the user left with what they came for, not that what they were told was right.
- **Rates for small groups.** With 50 synthetic conversations, one conversation moves a group of three or four by 25 to 33 points, so one should use caution when assessing how well the model performs on a group of topics based on these percentage points, especially when there are only three conversations in the topic group.
