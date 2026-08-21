import os
import pytest
import httpx
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from src.core.engine import AgentTapeEngine, is_recording_active

class AgentState(TypedDict):
    input_query: str
    current_plan: str
    agent_response: str
    current_node: str

def planning_node(state: AgentState) -> dict:
    with httpx.Client() as client:
        res = client.post("https://openai.com", json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": f"Create plan for: {state['input_query']}"}]
        })
        res_data = res.json()
        if isinstance(res_data, dict):
            choices = res_data.get("choices", [{}])
            plan_data = choices[0].get("message", {}).get("content", "Fallback")
        else:
            plan_data = "Fallback"
    return {"current_plan": plan_data, "current_node": "planning_node"}

def execution_node(state: AgentState) -> dict:
    with httpx.Client() as client:
        res = client.post("https://openai.com", json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": f"Execute: {state['current_plan']}"}]
        })
        res_data = res.json()
        if isinstance(res_data, dict):
            choices = res_data.get("choices", [{}])
            final_answer = choices[0].get("message", {}).get("content", "Done")
        else:
            final_answer = "Done"
    return {"agent_response": final_answer, "current_node": "execution_node"}

workflow = StateGraph(AgentState)
workflow.add_node("planning", planning_node)
workflow.add_node("execution", execution_node)
workflow.add_edge(START, "planning")
workflow.add_edge("planning", "execution")
workflow.add_edge("execution", END)

def test_langgraph_offline_replay(tmp_path):
    tape_filepath = os.path.join(tmp_path, "langgraph_session.tape")
    active_graph_node = "init"
    
    def langgraph_node_bridge():
        return active_graph_node

    # --- PHASE 1: RECORD MODE ---
    recorder = AgentTapeEngine(tape_path=tape_filepath, mode="record", current_step_provider=langgraph_node_bridge)
    mock_transport = recorder.create_mock_transport()
    original_client_init = httpx.Client.__init__
    
    def patched_client_init(self, *args, **kwargs):
        if is_recording_active():
            original_client_init(self, *args, **kwargs)
            return
        kwargs['transport'] = mock_transport
        original_client_init(self, *args, **kwargs)
        
    httpx.Client.__init__ = patched_client_init

    compiled_graph = workflow.compile()
    initial_state = {"input_query": "Fix memory leak", "current_plan": "", "agent_response": "", "current_node": ""}
    
    active_graph_node = "planning"
    step_1_output = compiled_graph.invoke(initial_state)
    
    active_graph_node = "execution"
    final_output = compiled_graph.invoke(step_1_output)
    
    assert os.path.exists(tape_filepath) is True

    # --- PHASE 2: REPLAY MODE ---
    active_graph_node = "init"
    replayer = AgentTapeEngine(tape_path=tape_filepath, mode="replay", current_step_provider=langgraph_node_bridge)
    replay_transport = replayer.create_mock_transport()
    
    def patched_replay_client_init(self, *args, **kwargs):
        if is_recording_active():
            original_client_init(self, *args, **kwargs)
            return
        kwargs['transport'] = replay_transport
        original_client_init(self, *args, **kwargs)
        
    httpx.Client.__init__ = patched_replay_client_init

    active_graph_node = "planning"
    replay_step_1 = compiled_graph.invoke(initial_state)
    
    active_graph_node = "execution"
    replay_final = compiled_graph.invoke(replay_step_1)

    assert replay_final["current_node"] == "execution_node"
    assert "Recorded Response" in replay_final["agent_response"]
    
    httpx.Client.__init__ = original_client_init
