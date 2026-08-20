import re
import json
from typing import Dict, Any

class SecurityScrubber:
    """Detects and scrubs PII, Bearer Tokens, and API secrets from payloads."""
    
    def __init__(self):
        # High-utility regex patterns for enterprise security compliance
        self.patterns = {
            "bearer_token": re.compile(r"Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*"),
            "api_key": re.compile(r"(sk-[a-zA-Z0-9]{32,})|(key-[a-zA-Z0-9]{32,})"),
            "email": re.compile(r"[\w\.-]+@[\w\.-]+\.\w+"),
            "generic_secret": re.compile(r'(?i)(password|secret|private_key|auth_token)"\s*:\s*"([^"]+)"')
        }

    def scrub_text(self, text: str) -> str:
        """Applies regex transformations to sanitize strings before disk write."""
        if not text:
            return text
        
        text = self.patterns["bearer_token"].sub("Bearer [REDACTED_SECRET]", text)
        text = self.patterns["api_key"].sub("[REDACTED_API_KEY]", text)
        text = self.patterns["email"].sub("[REDACTED_EMAIL]", text)
        
        # Scrub JSON key-value secrets safely
        text = self.patterns["generic_secret"].sub(r'"\1":"[REDACTED_DATA]"', text)
        return text

    def scrub_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deep-traverses dictionaries to sanitize structured JSON configurations."""
        dumped = json.dumps(data)
        scrubbed = self.scrub_text(dumped)
        return json.loads(scrubbed)
