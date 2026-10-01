"""
OpsPilot — PII Redactor
"""

import re
from typing import Any

# Regex patterns for common PII and secrets
REDACTION_PATTERNS = [
    # Emails
    (re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'), "***REDACTED_EMAIL***"),
    # Phone numbers (basic)
    (re.compile(r'\b\+?[\d\s-]{10,15}\b'), "***REDACTED_PHONE***"),
    # AWS Access Keys
    (re.compile(r'AKIA[0-9A-Z]{16}'), "***REDACTED_AWS_KEY***"),
    # Generic Bearer Tokens
    (re.compile(r'Bearer [A-Za-z0-9\-\._~\+/]+={0,2}'), "Bearer ***REDACTED_TOKEN***"),
]

def redact_string(text: str) -> str:
    """Redacts PII and secrets from a string."""
    if not isinstance(text, str):
        return text
    
    redacted = text
    for pattern, replacement in REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted

def redact_data(data: Any) -> Any:
    """Recursively redacts PII from strings in dictionaries and lists."""
    if isinstance(data, str):
        return redact_string(data)
    elif isinstance(data, dict):
        return {k: redact_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [redact_data(v) for v in data]
    return data
