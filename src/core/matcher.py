import re
import difflib

class SemanticMatcher:
    """Calculates prompt similarity scores to bypass non-deterministic updates."""
    
    def __init__(self, threshold: float = 0.92):
        self.threshold = threshold

    def _normalize(self, text: str) -> str:
        """Strips structural whitespace, dynamic system dates, and punctuation."""
        text = text.lower().strip()
        # Strip dynamic ISO timestamps often injected into modern agent plans
        text = re.sub(r"\d{4}-\d{2}-\d{2}t\d{2}:\d{2}:\d{2}(\.\d+)?z", "[TIMESTAMP]", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def calculate_similarity(self, prompt_a: str, prompt_b: str) -> float:
        """Computes structural token similarity using SequenceMatcher."""
        norm_a = self._normalize(prompt_a)
        norm_b = self._normalize(prompt_b)
        return difflib.SequenceMatcher(None, norm_a, norm_b).ratio()
