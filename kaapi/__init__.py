"""Kaapi: deterministic Claude Code and Codex configuration analysis."""

__version__ = "1.1.0"

from .analyze import analyze_text
from .model import ConfigError
from .policy import PolicyError

__all__ = ["__version__", "analyze_text", "ConfigError", "PolicyError"]
