

from fs_tools import read_file, write_file, list_files, search_in_file

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


TOOL_SCHEMAS = [
    {"type": "function", "function": READ_FILE_SCHEMA},
    {"type": "function", "function": WRITE_FILE_SCHEMA},
    {"type": "function", "function": LIST_FILES_SCHEMA},
    {"type": "function", "function": SEARCH_IN_FILE_SCHEMA},
]