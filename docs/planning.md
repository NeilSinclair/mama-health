# Planning Doc

Please feel free to use Fable 5 for writing any prompts and then Opus 5.5 for writing the code and doing the code review.

You should use prompt caching to save on costs. Please do one run to cache the prompt and then do this scoring async so you can score multiple conversations simultaneously.

Please use structured output for this, with pydantic classes.

I want you to do two versions - one with GPT Luna and the other with Haiku 4.5. I will judge between both of them and decide which one we use.

## Initial pipeline:

Write a script to summarise each conversation. The summaries should include:
- Main topics discussed: list[str]
- Summary of the conversation: str -> two or three short sentences 
- Disease mentioned: str -> deterministic copy
- User age, gender, location -> list - deterministic copy
- Reason for the conversation: str
- Potential customer pain points in the conversation: list[str]
- Boolean: whether the customer's issue was resolved: bool
- Reason the conversation was ended: str -> an interpretation (user complaint resolved?); include both deterministic reason and LLM-generated reason

## Process the summaries:

- Take the main topics discussed across the discussions and refine them such that there is a limited list of topics (i.e. maybe one topic for one conversation is "insomia" and for another it's "trouble sleeping", replace both with insomnia). You can use a dictionary to map original topics to refined ones

- Do the same for potential customer pain points, reason's the conversation was ended, reason for the conversation

- It's fine to still have unique labels; don't force two raw labels to be the same if they're not the same

- Discussions should be linked such that I can see all of the conversations when I click on a topic, customer pain point, reason the conversation was ended etc. When clicking on this on the UI, I can see the summaries of the conversations and then below that the other information capr

## Present these insights together in a UI

- Create an HTML-based UI for exploring these insights above

- Each article is presented as a row with the summary and the points captured. The user can click on a drop down to see the full conversation, rendered nicely. 

- The user can filter for the topics, potential pain points, reasons conversation was ended, reason for the conversation, disease from drop downs; they can also filter for these things by click on one of the potential pain points (etc.) in one of the conversation rows