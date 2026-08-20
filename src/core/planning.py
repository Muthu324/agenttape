import os
import json
from typing import Dict, Any, Optional
from src.core.security import SecurityScrubber
from src.core.matcher import SemanticMatcher

class PlanningGraphRouter:
    """Tracks agent branching trees to route queries accurately based on state context."""
    
    def __init__(self):
        self.tape_data: Dict[str, Any] = {"interactions": []}
        self.scrubber = SecurityScrubber()
        self.matcher = SemanticMatcher()

    def load_tape(self, file_path: str):
        """Loads a recorded execution tape from disk."""
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                self.tape_data = json.load(f)

    def save_tape(self, file_path: str):
        """Saves a fully sanitized execution tape back to the repository."""
        clean_tape = self.scrubber.scrub_dict(self.tape_data)
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(clean_tape, f, indent=2)

    def record_node(self, current_step: str, request_payload: Dict[str, Any], response_payload: Dict[str, Any]):
        """Appends a new structural node to the interaction sequence tree."""
        self.tape_data["interactions"].append({
            "step_id": len(self.tape_data["interactions"]) + 1,
            "agent_state_step": current_step,
            "request": request_payload,
            "response": response_payload
        })

    def find_mock_response(self, current_step: str, incoming_request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Matches context state & prompt similarity to retrieve mock data offline."""
        incoming_str = json.dumps(incoming_request.get("json", incoming_request.get("content", "")))
        best_match = None
        highest_score = 0.0

        for node in self.tape_data["interactions"]:
            # Context Filtering: Ensure we are evaluating the correct planning phase node
            if node["agent_state_step"] == current_step:
                recorded_str = json.dumps(node["request"].get("json", node["request"].get("content", "")))
                score = self.matcher.calculate_similarity(incoming_str, recorded_str)
                
                if score > highest_score:
                    highest_score = score
                    best_match = node["response"]

        if highest_score >= self.matcher.threshold:
            return best_match
        return None
