import json
from typing import Dict, Any, Optional, Callable
import httpx
from src.core.planning import PlanningGraphRouter

class AgentTapeEngine:
    """The unified core framework coordinator governing Record and Replay modes."""
    
    def __init__(self, tape_path: str, mode: str = "replay", current_step_provider: Optional[Callable[[], str]] = None):
        self.tape_path = tape_path
        self.mode = mode.lower()  # Accepts 'record' or 'replay'
        self.router = PlanningGraphRouter()
        
        # Callback linking directly into LangGraph state or AutoGen sequence tracking
        self.current_step_provider = current_step_provider or (lambda: "default_execution_node")
        
        if self.mode == "replay":
            self.router.load_tape(self.tape_path)

    def create_mock_transport(self) -> httpx.MockTransport:
        """Generates an isolated network sandbox intercepting outbound HTTP workloads."""
        
        def handle_request(request: httpx.Request) -> httpx.Response:
            current_step = self.current_step_provider()
            request.read()
            
            # Extract request metadata safely
            req_data = {
                "url": str(request.url),
                "method": request.method,
                "headers": dict(request.headers),
                "json": json.loads(request.content.decode()) if request.content else {}
            }

            if self.mode == "replay":
                mock_res = self.router.find_mock_response(current_step, req_data)
                if mock_res:
                    return httpx.Response(
                        status_code=mock_res.get("status_code", 200),
                        headers=mock_res.get("headers", {}),
                        content=json.dumps(mock_res.get("json", {})).encode()
                    )
                raise RuntimeError(
                    f"[AgentTape Error] Out of Sync! No matching mock found for step: '{current_step}'. "
                    f"Fuzzy Match score fell below threshold config."
                )
                
            elif self.mode == "record":
                # Real execution pass-through to upstream network channels
                with httpx.Client(transport=httpx.HTTPTransport()) as live_client:
                    live_res = live_client.send(request)
                    
                res_data = {
                    "status_code": live_res.status_code,
                    "headers": dict(live_res.headers),
                    "json": live_res.json() if live_res.headers.get("content-type") == "application/json" else live_res.text
                }
                
                # Log state machine checkpoint details onto tape
                self.router.record_node(current_step, req_data, res_data)
                self.router.save_tape(self.tape_path)
                return live_res

        return httpx.MockTransport(handle_request)
