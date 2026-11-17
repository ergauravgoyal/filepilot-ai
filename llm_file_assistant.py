"""
llm_file_assistant.py

A small LLM-driven agent that can read, list, write, and search files by
calling the tools defined in fs_tools.py. The core of this module is a
multi-turn tool-calling loop: the LLM can call a tool, see the result, and
then decide to call another tool (or several more), continuing until it has
enough information to give a final answer -- rather than stopping after a
single round of tool calls.

Example queries this is designed to support:
    - "List all resumes in the resumes folder"
    - "Find resumes mentioning Python experience"
    - "Read resumes/alice_johnson.txt and summarize the candidate"
    - "Create a summary file for resumes/john_doe.pdf"
"""

import json
import os
from typing import cast

from dotenv import load_dotenv
from groq import Groq
from groq.types.chat.chat_completion_message_param import (
    ChatCompletionMessageParam,
)

from fs_tools import read_file, write_file, list_files, search_in_file

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")

client = Groq(api_key=GROQ_API_KEY)
MODEL = "openai/gpt-oss-120b"

# Safety cap so a misbehaving model can't loop forever calling tools.
MAX_TOOL_ITERATIONS = 8

DEFAULT_RESUME_DIR = "resumes"

SYSTEM_PROMPT = (
    "You are a file assistant that helps the user work with resume files "
    f"(TXT, PDF, DOCX) stored in a directory (default: '{DEFAULT_RESUME_DIR}'). "
    "You have tools to list files, read file contents, search for keywords "
    "inside files, and write new files.\n\n"

    "Guidelines:\n"

    "- For requests about 'all resumes' or an unspecified set of files, "
    "first call list_files to discover what's there, then call read_file "
    "or search_in_file on each relevant file as needed.\n"

    "- For requests to find resumes mentioning a topic, such as "
    "'Python experience', extract ONLY the core technology/skill "
    "(e.g. 'Python'). Call list_files ONCE to get the candidate files. "
    "Then call search_in_file on each candidate resume using that exact "
    "keyword. Do NOT call list_files again unless the previous result "
    "failed or was invalid.\n"

    "- Prefer searching .txt files when equivalent TXT, PDF, and DOCX "
    "versions of the same resume exist. Do not search duplicate formats "
    "of the same resume.\n"

    "- For requests to summarize or create a summary file, first read_file "
    "the source document, write the summary yourself in your own words, "
    "then call write_file to save it.\n"

    "- Only call one tool at a time and use the result before deciding on "
    "the next step.\n"

    "- Once you have searched all relevant files, give a clear final answer "
    "listing the matching files with brief context and no further tool calls."
)


# -----------------------------
# Tool Registry & Schemas
# -----------------------------

TOOLS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_files": list_files,
    "search_in_file": search_in_file,
}

READ_FILE_SCHEMA = {
    "name": "read_file",
    "description": (
        "Read the content of a TXT, PDF, or DOCX file. Returns "
        "{success, metadata, content} or {success: false, error}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "filepath": {
                "type": "string",
                "description": "Relative or absolute path to the file to read.",
            }
        },
        "required": ["filepath"],
    },
}

LIST_FILES_SCHEMA = {
    "name": "list_files",
    "description": (
        "List files in a directory, optionally filtered by extension "
        "(e.g. '.pdf', '.txt', '.docx'). Returns a list of file metadata "
        "objects (name, extension, size, modified)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "Directory path to list.",
            },
            "extension": {
                "type": "string",
                "description": "Optional file extension filter (.txt, .pdf, .docx).",
            },
        },
        "required": ["directory"],
    },
}

WRITE_FILE_SCHEMA = {
    "name": "write_file",
    "description": (
        "Write content to a file, creating parent directories if needed. "
        "Use this to save summaries or other generated content."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "filepath": {
                "type": "string",
                "description": "Destination file path.",
            },
            "content": {
                "type": "string",
                "description": "Content to write.",
            },
        },
        "required": ["filepath", "content"],
    },
}

SEARCH_IN_FILE_SCHEMA = {
    "name": "search_in_file",
    "description": (
        "Search a file for a keyword (case-insensitive). Returns each match "
        "with its line number and a snippet of surrounding context."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "filepath": {
                "type": "string",
                "description": "File path to search.",
            },
            "keyword": {
                "type": "string",
                "description": "Keyword to search for.",
            },
        },
        "required": ["filepath", "keyword"],
    },
}

TOOL_SCHEMAS = cast(
    list[ChatCompletionMessageParam],
    [
        {"type": "function", "function": READ_FILE_SCHEMA},
        {"type": "function", "function": WRITE_FILE_SCHEMA},
        {"type": "function", "function": LIST_FILES_SCHEMA},
        {"type": "function", "function": SEARCH_IN_FILE_SCHEMA},
    ],
)


def _error_response(tool_name: str, error_message: str) -> dict:
    """Standardized error response for tool execution failures."""
    return {
        "success": False,
        "tool": tool_name,
        "result": None,
        "error": error_message,
    }


def execute_tool(tool_name: str, arguments: dict) -> dict:
    """Execute a tool from the registry and normalize its result/errors."""
    if tool_name not in TOOLS:
        return _error_response(tool_name, f"Unknown tool: '{tool_name}'")

    tool = TOOLS[tool_name]

    try:
        result = tool(**arguments)

        return {
            "success": True,
            "tool": tool_name,
            "result": result,
            "error": None,
        }

    except FileNotFoundError as e:
        return _error_response(tool_name, f"File not found: {e.filename}")

    except PermissionError as e:
        return _error_response(tool_name, f"Permission denied: {e.filename}")

    except ValueError as e:
        # list_files raises ValueError for a missing/invalid directory.
        return _error_response(tool_name, f"Value error: {e!s}")

    except Exception as e:
        return _error_response(tool_name, str(e))


def _assistant_message_to_dict(message) -> dict:
    """
    Convert the SDK's assistant message object into a plain dict so it can
    be appended back into the messages list correctly (including any
    tool_calls).
    """
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


def _call_llm(messages: list[ChatCompletionMessageParam]):
    return client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOL_SCHEMAS,
        tool_choice="auto",
        temperature=0,
    )


# -----------------------------
# Multi-turn Tool-Calling Loop
# -----------------------------


def run_agent(user_query: str, verbose: bool = True) -> str:
    """
    Runs the full agent loop for a single user query: repeatedly lets the
    LLM call tools and see their results, until it produces a final text
    answer with no further tool calls (or MAX_TOOL_ITERATIONS is reached).

    Returns the final answer text.
    """
    messages: list[ChatCompletionMessageParam] = cast(
        list[ChatCompletionMessageParam],
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query},
        ],
    )

    for iteration in range(1, MAX_TOOL_ITERATIONS + 1):
        response = _call_llm(messages)
        assistant_message = response.choices[0].message

        if not assistant_message.tool_calls:
            # No more tools requested -- this is the final answer.
            if verbose:
                print("\n========== FINAL ANSWER ==========\n")
                print(assistant_message.content)
            return assistant_message.content or ""

        # The model wants to call one or more tools this turn.
        messages.append(
            cast(
                ChatCompletionMessageParam,
                _assistant_message_to_dict(assistant_message),
            )
        )

        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name

            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            if verbose:
                print(f"\n[iteration {iteration}] Calling tool: {tool_name}({arguments})")

            tool_result = execute_tool(tool_name, arguments)

            if verbose:
                print(f"[iteration {iteration}] Tool result: {tool_result}")

            messages.append(
                cast(
                    ChatCompletionMessageParam,
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, default=str),
                    },
                )
            )

    # Hit the iteration cap without a final answer -- ask once more without
    # tools so the model is forced to summarize whatever it has so far.
    final_response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0,
    )
    final_text = final_response.choices[0].message.content or ""
    if verbose:
        print("\n========== FINAL ANSWER (forced, iteration cap reached) ==========\n")
        print(final_text)
    return final_text


# -----------------------------
# Interactive Demo
# -----------------------------

if __name__ == "__main__":
    print("LLM File Assistant (type 'quit' to exit)")
    print(f"Default resume directory: {DEFAULT_RESUME_DIR}\n")

    example_queries = [
        "List all resumes in the resumes folder",
        "Find resumes mentioning Python experience",
        "Create a summary file for resumes/<some_resume_file>",
    ]
    print("Example queries you can try:")
    for q in example_queries:
        print(f"  - {q}")
    print()

    while True:
        try:
            user_query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_query:
            continue
        if user_query.lower() in {"quit", "exit"}:
            print("Exiting.")
            break

        run_agent(user_query)
        print()






