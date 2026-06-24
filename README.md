# AI Personal Assistant

A modular Python chat assistant powered by the OpenAI API. Chat from the terminal, keep conversation history across sessions, and customize behavior via a system prompt file.

## Features

- Interactive CLI chat with OpenAI
- Persistent conversation history (`data/conversation.json`)
- System instructions loaded from `config/system_prompt.txt`
- Secure configuration via `.env`
- Modular architecture (config, prompts, memory, AI logic, UI)

## Project Structure

```
AI-Personal-Assistant/
├── src/
│   ├── main.py           # CLI entry point
│   ├── ai_assistant.py   # OpenAI orchestration
│   ├── config.py         # Environment and path settings
│   ├── memory.py         # Conversation persistence
│   └── prompts.py        # System prompt loader
├── config/
│   └── system_prompt.txt # AI behavior instructions
├── data/
│   └── conversation.json # Saved chat history
├── .env                  # API keys (not committed)
├── requirements.txt
└── README.md
```

## Installation

### 1. Prerequisites

- Python 3.12+
- An [OpenAI API key](https://platform.openai.com/api-keys)

### 2. Clone or open the project

```bash
cd AI-Personal-Assistant
```

### 3. Create a virtual environment (recommended)

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

Edit `.env` and set your OpenAI API key:

```env
OPENAI_API_KEY=sk-your-actual-key-here
OPENAI_MODEL=gpt-4o-mini
```

## How to Run

From the project root, with your virtual environment activated:

```bash
python src/main.py
```

### CLI Commands

| Command | Action |
|---------|--------|
| Type a message | Send it to the assistant |
| `clear` | Reset conversation history |
| `quit` or `exit` | Exit the application |

## Customization

- **System behavior**: Edit `config/system_prompt.txt`
- **Model**: Change `OPENAI_MODEL` in `.env` (e.g. `gpt-4o`, `gpt-3.5-turbo`)
- **History**: Stored automatically in `data/conversation.json`

## Architecture

| Module | Layer | Responsibility |
|--------|-------|----------------|
| `config.py` | Configuration | Load `.env`, define paths |
| `prompts.py` | AI logic | Read system instructions |
| `memory.py` | Data handling | Load/save conversation JSON |
| `ai_assistant.py` | AI logic | Build messages, call OpenAI |
| `main.py` | User interface | CLI chat loop |

## License

MIT
