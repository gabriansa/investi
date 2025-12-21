# Agent Tools
from pathlib import Path


def load_prompt(filename: str) -> str:
    """Load a prompt template from the tools/prompts directory."""
    return (Path(__file__).parent / "prompts" / filename).read_text()
