"""One place for settings: model, Portkey, paths, loop limits."""

import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

BACKEND_DIR = Path(__file__).resolve().parent
HW5_DIR = BACKEND_DIR.parent
PROMPT_DIR = BACKEND_DIR / "prompts"
MCP_CONFIG = HW5_DIR / ".mcp.json"
AUDIT_FILE = HW5_DIR / "output" / "audit_trail.json"

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
load_dotenv(HW5_DIR / ".env")
load_dotenv(HW5_DIR.parent / ".env")  # PORTKEY_API_KEY lives in the class-folder root

PORTKEY_BASE_URL = "https://api.portkey.ai/v1"


def mcp_client_config() -> dict:
    """.mcp.json with its repo-relative paths resolved against hw5/.

    The file stays portable (no machine paths), and the backend can still
    launch the server when uvicorn runs from backend/.
    """
    cfg = json.loads(MCP_CONFIG.read_text())
    for server in cfg["mcpServers"].values():
        cmd = HW5_DIR / server["command"]
        if cmd.exists():
            server["command"] = str(cmd)
        server["args"] = [str(HW5_DIR / a) if (HW5_DIR / a).exists() else a for a in server.get("args", [])]
        server["cwd"] = str(HW5_DIR)
    return cfg

# HW5 rule: every agent uses gpt-6-luna and nothing else.
ALLOWED_MODEL = "gpt-6-luna"
MODEL_NAME = os.getenv("OPENAI_MODEL", ALLOWED_MODEL)
if MODEL_NAME != ALLOWED_MODEL:
    raise RuntimeError(f"OPENAI_MODEL={MODEL_NAME!r}, but HW5 allows only {ALLOWED_MODEL!r}.")

# Loop and token guards. One budget is shared by the whole team for a run (delegated
# runs draw from the caller's budget), so full connectivity can't ping-pong forever.
MAX_DELEGATION_DEPTH = int(os.getenv("MAX_DELEGATION_DEPTH", "3"))
REQUEST_LIMIT = int(os.getenv("AGENT_REQUEST_LIMIT", "40"))         # model calls per team run
TOOL_CALLS_LIMIT = int(os.getenv("AGENT_TOOL_CALLS_LIMIT", "60"))    # tool calls per team run
TOKEN_LIMIT = int(os.getenv("AGENT_TOKEN_LIMIT", "150000"))          # total tokens per team run
MODEL_TIMEOUT = float(os.getenv("MODEL_TIMEOUT", "90"))  # seconds per model call; a stalled call is retried


@lru_cache
def get_model() -> OpenAIResponsesModel:
    """The single model client every agent shares, routed through Portkey."""
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is missing. Add it to hw5/.env or the class-folder .env.")
    client = AsyncOpenAI(api_key=api_key, base_url=PORTKEY_BASE_URL,
                         timeout=MODEL_TIMEOUT, max_retries=2)
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
