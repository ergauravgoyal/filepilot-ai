import json
from typing import cast

from groq.types.chat import ChatCompletionMessageParam

from app.agent.prompts import SYSTEM_PROMPT
from app.config import MAX_TOOL_ITERATIONS, MODEL
from app.llm.client import call_llm
from app.tools.registry import execute_tool
from app.tools.schemas import TOOL_SCHEMAS


def assistant_message_to_dict(message) -> dict:
    msg = {
        "role": "assistant",
        "content": message.content,
    }

    if message.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in message.tool_calls
        ]

    return msg

def run_agent(user_query: str, verbose: bool = True) -> str:

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_query,
        },
    ]

    for iteration in range(1, MAX_TOOL_ITERATIONS + 1):

        response = call_llm(
            messages,
            TOOL_SCHEMAS,
        )

        assistant_message = response.choices[0].message

        # LLM has finished
        if not assistant_message.tool_calls:

            if verbose:
                print("\n========== FINAL ANSWER ==========\n")
                print(assistant_message.content)

            return assistant_message.content or ""

        # Save LLM's tool request
        messages.append(
            cast(
                ChatCompletionMessageParam,
                assistant_message_to_dict(assistant_message),
            )
        )

        # Execute requested tool
        for tool_call in assistant_message.tool_calls:

            tool_name = tool_call.function.name

            try:
                arguments = json.loads(
                    tool_call.function.arguments
                )
            except json.JSONDecodeError:
                arguments = {}

            if verbose:
                print(
                    f"\n[iteration {iteration}] "
                    f"Calling tool: {tool_name}({arguments})"
                )

            tool_result = execute_tool(
                tool_name,
                arguments,
            )

            if verbose:
                print(
                    f"[iteration {iteration}] "
                    f"Tool result: {tool_result}"
                )

            # Send result back to LLM
            messages.append(
                cast(
                    ChatCompletionMessageParam,
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(
                            tool_result,
                            default=str,
                        ),
                    },
                )
            )

    return "Agent reached the maximum number of iterations."