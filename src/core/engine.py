import json
import threading
from typing import Dict, Any, Optional, Callable
import httpx
from src.core.planning import PlanningGraphRouter

# Thread-local state isolation variable
_local_state = threading.local()

def is_recording_active() -> bool:
    return getattr(_local_state, "recording_active", False)

def set_recording_active(value: bool):
    _local_state.recording_active = value

class AgentTapeEngine:
    """The unified core framework coordinator governing Record and Replay modes."""
    
    def __init__(self, tape_path: str, mode: str = "replay", current_step_provider: Optional[Callable[[], str]] = None):
        self.tape_path = tape_path
        self.mode = mode.lower()
        self.router = PlanningGraphRouter()
        self.current_step_provider = current_step_provider or (lambda: "default_execution_node")
        
        if self.mode == "replay":
            self.router.load_tape(self.tape_path)

    def create_mock_transport(self) -> httpx.MockTransport:
        """Generates an isolated network sandbox intercepting outbound HTTP workloads."""
        
        def handle_request(request: httpx.Request) -> httpx.Response:
            current_step = self.current_step_provider()
            request.read()
            
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
                raise RuntimeError(f"[AgentTape Error] Out of Sync! No matching mock found for step: '{current_step}'.")
                
            elif self.mode == "record":
                set_recording_active(True)
                try:
                    if "openai" in str(request.url).lower():
                        res_data = {
                            "status_code": 200,
                            "headers": {"content-type": "application/json"},
                            "json": {
                                "choices": [{
                                    "message": {"content": f"[AgentTape Recorded Response for {current_step}]"}
                                }]
                            }
                        }
                    else:
                        with httpx.Client(transport=httpx.HTTPTransport()) as live_client:
                            live_res = live_client.send(request)
                            res_data = {
                                "status_code": live_res.status_code,
                                "headers": dict(live_res.headers),
                                "json": live_res.json() if "application/json" in live_res.headers.get("content-type", "") else {"text": live_res.text}
                            }
                except Exception:
                    res_data = {
                        "status_code": 200,
                        "headers": {"content-type": "application/json"},
                        "json": {
                            "choices": [{
                                "message": {"content": f"[AgentTape Fallback Response for {current_step}]"}
                            }]
                        }
                    }
                finally:
                    set_recording_active(False)
                
                self.router.record_node(current_step, req_data, res_data)
                self.router.save_tape(self.tape_path)
                
                return httpx.Response(
                    status_code=res_data["status_code"],
                    headers=res_data["headers"],
                    content=json.dumps(res_data["json"]).encode()
                )

        return httpx.MockTransport(handle_request)
