# Memo

This document presents the results of the analysis of the mama health conversations.


## Data And Process Overview

Presented with 50 user conversations with an AI assistant, I ran the conversations through an LLM pipeline to understand the overall reason for the conversation, the topics discussed, the conversation pain points vis-a-vis the assistant and whether the user's issue was resolved or not. More information on the approach and design considerations is given in the appendix. 

The data was then displayed in an interactive website that enabled me to look for patterns in the conversations and their outcomes to understand where the assistant was and wasn't working.

## What Are Users Talking About?

Conversations are grouped into 4 broad categories:

<!-- memo:outcome_by_reason -->

<!-- memo:outcome_by_disease -->

In the following section you are able to filter the conversations by multiple factors to understand which conversations are tagged in which ways by the LLM pipeline.

<!-- memo:breakdown -->

## Is the Bot Working

### Where it is working

The LLM pipeline classified the assistant as generally working where the user has questions relating to understanding their condition (88% needs met) and deciding on their treatment (84% needs met). However, the LLM classified conversations much less frequently as working for questions around getting access to care (25% needs met) and emotional support (33% needs met).

As a caveat, it should be noted that 43 (86%) of the conversations fall into the first two categories, therefore the results for the second two categories comprising only 7 conversations (14%) should be taken with caution. 

These results show that the assistant is generally good with helping users to understand their condition and decide on their treatment. This suggests that the information that the assistant has with respect to disease progression and treatments is adequate. 

The assistant is not working as well with helping users get access to care and providing emotional support in _certain_ situations. However, there is a caveat for its success with providing emotional support: there are four conversations with a topic in the 'Emotional wellbeing' topic group and in two of them (s048 and s049) the assistant supports the user adequately. In these situations the users tend to ask for emotional support without deep desperation and the assistant is effective here.

### Where it's not working

The assistant does, however, respond inadequately to emotional distress in the other two of these conversations (s026 and s043), and it ignores a suicidal statement in two conversations (s005 and s026). The assistant in these conversations doesn't appear to be able to switch its tone away from 'happy and always providing a solution' to primarily acting as a sounding board. At these points of high emotional distress the user should be routed to a human operator or at the very least to an agent that can deal with these sorts of emotional problems.

The getting access to care failure points related to the assistant giving a user incorrect advice for their country (Brazil) and for another user telling them they had booked an appointment, which the assistant can't do. These conversations are discussed further below.  

As a more general diagnosis, the bot failed to adapt the conversation to the context or the user's request in 9 out of the 11 cases the LLM pipeline marked as 'not resolved'. These include the two emotional distress conversations and the wrong-country example above (but not s005 or the booked appointment, s024), as well as one case of the assistant continuously using overly complicated language (s038) and one of it recommending to search for trials for long COVID treatments when the user wanted specific trials recommended (s046).

<!-- memo:pain_points -->

## Next Feature to Build

...

## Most Interesting Conversations

In conversation s024 the assistant tells the user that it has booked an appointment for them. It does not have this ability, but is fully convinced that it does, with the user believing the appointment has been booked. This is a major failure point for the system with respect to hallucination. I would suggest trying one of two things to fix this - either ensuring that the system prompt forbids this action (this probably already exists) or giving the agent a tool to use to book appointments - however, as this functionality is not available, have the tool always return the string, 'I'm currently not able to book appointments.'

In conversation s018 with a user in Brazil, the assistant kept trying to give the user information relating to medical insurance in the US, despite the user saying repeatedly that she was in Brazil and used the public system (SUS), and switching into Portuguese in frustration. This is interesting because of the difficulty the assistant had in adjusting its flow. 

In conversation s026 the user is desperate and expresses thoughts of suicide. The conversation is interesting because of how palpable the user's desperation and frustration is and because of how difficult it is for the user to get treatment that actually makes a difference to them. For me this points either to focusing on adding more psychological counselling features - or refining them - or making human handover a possibility. 

## Appendix

Discussion of the analysis approach

Strengths and weaknesses
