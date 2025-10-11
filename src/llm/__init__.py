"""
LLM Interface layer for SQL-of-Thought framework.

Provides unified interfaces for different LLM providers (Anthropic, OpenAI, HuggingFace)
with consistent API, cost tracking, and error handling.
"""

from .base import BaseLLM

# Lazy imports to avoid dependency issues
def get_anthropic_interface():
    from .anthropic_interface import AnthropicInterface
    return AnthropicInterface

def get_openai_interface():
    from .openai_interface import OpenAIInterface
    return OpenAIInterface

def get_ollama_interface():
    from .ollama_interface import OllamaInterface
    return OllamaInterface

def get_llm_factory():
    from .llm_factory import LLMFactory
    return LLMFactory

# For backward compatibility, still expose direct imports
try:
    from .anthropic_interface import AnthropicInterface
except ImportError:
    AnthropicInterface = None

try:
    from .openai_interface import OpenAIInterface
except ImportError:
    OpenAIInterface = None

try:
    from .ollama_interface import OllamaInterface
except ImportError:
    OllamaInterface = None

try:
    from .llm_factory import LLMFactory
except ImportError:
    LLMFactory = None

__all__ = [
    "BaseLLM",
    "AnthropicInterface", 
    "OpenAIInterface",
    "OllamaInterface",
    "LLMFactory",
    "get_anthropic_interface",
    "get_openai_interface", 
    "get_ollama_interface",
    "get_llm_factory"
]