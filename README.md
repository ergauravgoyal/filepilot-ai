# FilePilot AI

**FilePilot AI** is a lightweight LLM-powered file assistant that uses
**Groq's LLaMA 3.3 70B** (free tier) to read, list, write, and search resume files via LLM function calling.

## Features

- 📄 **Read** TXT, PDF, and DOCX resume files
- 📁 **List** files in a directory with optional extension filter
- ✍️ **Write** generated summaries back to disk
- 🔍 **Search** for keywords inside files with context snippets
- 🤖 **Multi-turn tool loop** — the LLM keeps calling tools until it has a complete answer

## Project Structure

```
ll-powered-file-assistant/
├── fs_tools.py           # Part A: Core file-system tools
├── llm_file_assistant.py # Part B: LLM agent using Groq + tool calling
├── resumes/              # 10 sample resumes (TXT, PDF, DOCX formats)
├── requirements.txt
├── .env                  # GROQ_API_KEY goes here
└── README.md
```

## Setup

### 1. Create and activate a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure your API key
The project uses [Groq](https://console.groq.com) (free, no credit card needed).

```bash
cp .env.example .env
# Then edit .env and paste your GROQ_API_KEY
```

Or export it directly:
```bash
export GROQ_API_KEY=gsk_...
```

## Usage

### Interactive assistant
```bash
python llm_file_assistant.py
```

Example queries:
```
You: List all resumes in the resumes folder
You: Find resumes mentioning Python experience
You: Read resumes/Alice_Johnson_resume.txt and summarize the candidate
You: Create a summary file for resumes/Henry_Moore_resume.pdf
You: Search for candidates with machine learning skills
```

### Use tools directly (Part A)
```python
from fs_tools import read_file, list_files, write_file, search_in_file

# List all PDFs
files = list_files("resumes", extension=".pdf")

# Read a resume
result = read_file("resumes/Alice_Johnson_resume.txt")
print(result["content"])

# Keyword search
hits = search_in_file("resumes/Alice_Johnson_resume.txt", keyword="Python")
print(hits["matches"])

# Write a file
write_file("outputs/summary.txt", "Alice Johnson — Senior Python Developer...")
```

## Tool Reference (Part A — `fs_tools.py`)

| Function | Signature | Returns |
|---|---|---|
| `read_file` | `(filepath: str) → dict` | `{success, content, metadata}` |
| `list_files` | `(directory: str, extension: str = None) → list` | List of `{name, size, modified, extension}` |
| `write_file` | `(filepath: str, content: str) → dict` | `{success, message, metadata}` |
| `search_in_file` | `(filepath: str, keyword: str) → dict` | `{success, matches, match_count}` |

All functions handle errors gracefully and return `{success: False, error: "..."}` on failure.

## Sample Resumes

The `resumes/` folder includes 10 candidates in TXT, PDF, and DOCX formats:

| Candidate | Domain |
|---|---|
| Alice Johnson | Python / Data Engineering |
| Brian Smith | Frontend / React |
| Carol Davis | Machine Learning |
| David Wilson | DevOps / Kubernetes |
| Emma Brown | Product Management |
| Frank Miller | Backend / Django |
| Grace Taylor | Data Analyst |
| Henry Moore | Full Stack |
| Isabella Thomas | Cloud / AWS |
| Jack Anderson | AI / NLP |

## Dependencies

- `groq` — Groq API client (LLaMA 3.3 70B)
- `pdfplumber` — PDF text extraction
- `python-docx` — DOCX parsing
- `python-dotenv` — `.env` file loading

## Running as a standalone application
To test this specific assignment module individually, simply run:
```bash
source .venv/bin/activate
python llm_file_assistant.py
```
This is fully self-contained and does not require the other projects to be running.
