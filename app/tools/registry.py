from fs_tools import (
    read_file,
    write_file,
    list_files,
    search_in_file,
)

TOOLS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_files": list_files,
    "search_in_file": search_in_file,
}

def _error_response(tool_name: str, error_message: str) -> dict:
    return {
        "success": False,
        "tool": tool_name,
        "result": None,
        "error": error_message,
    }


def execute_tool(tool_name: str, arguments: dict) -> dict:

    if tool_name not in TOOLS:
        return _error_response(
            tool_name,
            f"Unknown tool: '{tool_name}'"
        )

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
        return _error_response(
            tool_name,
            f"File not found: {e.filename}"
        )

    except PermissionError as e:
        return _error_response(
            tool_name,
            f"Permission denied: {e.filename}"
        )

    except ValueError as e:
        return _error_response(
            tool_name,
            f"Value error: {e!s}"
        )

    except Exception as e:
        return _error_response(tool_name, str(e))