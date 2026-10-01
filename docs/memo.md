# Memo

This document presents the results of the analysis of the mama health conversations.


## Data And Process Overview

Presented with 50 user conversations with an AI assistant, I ran the converstions through an LLM pipeline to understand the overall reason for the conversation, the topics discussed, the conversation pain points vis-a-vis the assistant and whether the user's issue was resolved or not. More information on the approach and design considerations is given in the appendix. 

The data was then displayed in an interactive website than enabled me to look for patterns in the conversations and their outcomes to understand where the assistant was and wasn't working.

## What Are Users Talking About?

Conversations are grouped into 4 broad categories:

<!-- memo:outcome_by_reason -->

<!-- memo:outcome_by_disease -->

<!-- memo:breakdown -->

## Is the Bot Working

### Where it is working

The LLM pipeline classified the assistant as generally working where the user has questions relating to understanding their condition (86% needs met) and deciding on their treatment (85% needs met). However, the LLM classified conversations as generally working for questions around getting access to care (40% needs met) and emotional support (33% needs met) much less frequently. 

As a caveat, it should be noted that 42 (84%) of the conversations fall into the first two categories, therefore the results for the second two categories comprising only 8 conversations (16%) should be taken with caution. 

These results show that the assistant is generally good with helping users to understand their condition and decide on thie treatment, but is not working as well with helping users get access to care and providing emotional support in charged situations.

A major failure point for the assistant is ignoring emotional distress, including users talking about wanting to commit suicide. At these points of high emotional distress the user should be routed to a human operator or at the very least to an agent that can deal with these sorts of emotional problems.

The getting access to care failure points related to the assistant giving a user incorrect advice for their country (Brasil) and for another user telling them they had booked an appointment, which the assistant can't do.     

<!-- memo:pain_points -->

## Next Feature to Build

The 

## Most Interesting Conversations

In conversation s... the assistant tells the user that it has booked an appointment for the user. It does not have this ability, but is fully convinced that it does, with the user believing the appointment has been booked. This is a major failure point for the system with respect to hallucination.

## Appendix

Discussion of the analysis approach

Strengths and weaknesses
