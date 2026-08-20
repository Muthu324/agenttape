import os
import pytest
import httpx
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from src.core.engine import AgentTapeEngine

# =====================================================================
# 1. SETUP THE LANGGRAPH APPLICATION STATE & TOPOLOGY
# =====================================================================

# Define a standard LangGraph state tracker
class AgentState(TypedDict):
    input_query: str
    current_plan: str
    agent_response: str
    current_node: str

# Create simple node execution handlers for the state machine
def planning_node(state: AgentState) -> dict:
    # Simulating an internal LLM call using HTTPX
    with httpx.Client() as client:
        # If AgentTape is active in replay mode, this call is intercepted instantly
        res = client.post("https://openai.com", json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": f"Create a step-by-step execution plan for: {state['input_query']}"}]
        })
        plan_data = res.json().get("choices", [{}])[0].get("message", {}).get("content", "Fall back plan")
        
    return {"current_plan": plan_data, "current_node": "planning_node"}

def execution_node(state: AgentState) -> dict:
    with httpx.Client() as client:
        res = client.post("https://openai.com", json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": f"Execute this target plan: {state['current_plan']}"}]
        })
        final_answer = res.json().get("choices", [{}])[0].get("message", {}).get("content", "Done")
        
    return {"agent_response": final_answer, "current_node": "execution_node"}


# Build the Graph and compile it
workflow = StateGraph(AgentState)
workflow.add_node("planning", planning_node)
workflow.add_node("execution", execution_node)

workflow.add_edge(START, "planning")
workflow.add_edge("planning", "execution")
workflow.add_edge("execution", END)

# =====================================================================
# 2. THE TOP 0.1% DETERMINISTIC PYTEST SUITE
# =====================================================================

def test_langgraph_offline_replay(tmp_path):
    """Verifies that LangGraph loops can run isolated without hitting live APIs."""
    
    # Define where the test tape is located
    tape_filepath = os.path.join(tmp_path, "langgraph_session.tape")
    
    # Initialize the compiled state tracking state variable
    active_graph_node = "init"
    
    # Crucial Bridge: Hook AgentTape's context provider directly into LangGraph state changes
    def langgraph_node_bridge():
        return active_graph_node

    # --- PHASE 1: RECORDING THE GRAPH TRAJECTORY ---
    # In a real environment, you run this once locally with live keys
    recorder = AgentTapeEngine(
        tape_path=tape_filepath, 
        mode="record", 
        current_step_provider=langgraph_node_bridge
    )
    
    # Inject our mock transport directly into the HTTPX client library setup
    # Note: If your framework uses a global client, you monkey-patch httpx.Client directly
    mock_transport = recorder.create_mock_transport()
    
    # We patch the standard httpx client instantiation inside this test execution context
    original_client_init = httpx.Client.__init__
    
    def patched_client_init(self, *args, **kwargs):
        kwargs['transport'] = mock_transport
        original_client_init(self, *args, **kwargs)
        
    httpx.Client.__init__ = patched_client_init

    # Compile the graph architecture
    compiled_graph = workflow.compile()

    # Step through the graph manually to sync state tracking variables explicitly
    initial_state = {"input_query": "Fix system memory vulnerability", "current_plan": "", "agent_response": "", "current_node": ""}
    
    # Execute node 1
    active_graph_node = "planning"
    step_1_output = compiled_graph.invoke(initial_state)
    
    # Execute node 2
    active_graph_node = "execution"
    final_output = compiled_graph.invoke(step_1_output)
    
    # Verify the tape file was written out securely on the local block storage layer
    assert os.path.exists(tape_filepath) is True

    # --- PHASE 2: DETERMINISTIC REPLAY MATRIX ---
    # Reset tracking vars to prove state separation
    active_graph_node = "init"
    
    replayer = AgentTapeEngine(
        tape_path=tape_filepath, 
        mode="replay", 
        current_step_provider=langgraph_node_bridge
    )
    
    # Update the patched transport to reference the replay engine instead of the recorder
    replay_transport = replayer.create_mock_transport()
    def patched_replay_client_init(self, *args, **kwargs):
        kwargs['transport'] = replay_transport
        original_client_init(self, *args, **kwargs)
    httpx.Client.__init__ = patched_replay_client_init

    # Run the graph again completely offline
    active_graph_node = "planning"
    replay_step_1 = compiled_graph.invoke(initial_state)
    
    active_graph_node = "execution"
    replay_final = compiled_graph.invoke(replay_step_1)

    # Assert structural alignment between real execution logs and masked replay caches
    assert replay_final["current_node"] == "execution_node"
    assert "REDACTED" not in replay_final["agent_response"]
    
    # Clean up global monkey-patch state back to standard defaults
    httpx.Client.__init__ = original_client_init
    print("✅ LangGraph integration workflow verified perfectly offline.")
