from groq import Groq

from app.config import GROQ_API_KEY, MODEL

client = Groq(api_key=GROQ_API_KEY)


def call_llm(messages, tools):
    return client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        temperature=0,
    )