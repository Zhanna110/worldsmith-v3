import os
from typing import TypedDict, Annotated, List, Union, Literal
from langgraph.graph import StateGraph, END
from google import genai
from google.genai import types

# Define the state of the agent
class AgentState(TypedDict):
    messages: List[str]
    current_draft: str
    critique_count: int

# Initialize the Google GenAI Client
# Assumes GOOGLE_API_KEY is set in environment variables
client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

def supervisor_node(state: AgentState) -> dict:
    """
    The Supervisor node decides the next step based on the current state.
    It uses Gemini 3 Pro to make the decision.
    """
    messages = state.get("messages", [])
    current_draft = state.get("current_draft", "")
    critique_count = state.get("critique_count", 0)

    prompt = f"""
    You are a supervisor managing a writing process.
    Current Draft: {current_draft}
    Critique Count: {critique_count}
    Messages: {messages}

    Decide the next step:
    - If there is no draft, call 'Writer'.
    - If there is a draft and critique_count < 3, call 'Editor'.
    - If the draft is good enough or critique_count >= 3, call 'FINISH'.

    Respond with ONLY one word: 'Writer', 'Editor', or 'FINISH'.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0
        )
    )|
    
    decision = response.text.strip()
    
    # Fallback/Safety in case of unexpected output
    if decision not in ["Writer", "Editor", "FINISH"]:
        # Simple logic fallback
        if not current_draft:
            decision = "Writer"
        elif critique_count < 3:
            decision = "Editor"
        else:
            decision = "FINISH"

    return {"messages": messages + [f"Supervisor decided: {decision}"]}

def writer_node(state: AgentState) -> dict:
    """
    The Writer node generates or revises the draft.
    """
    messages = state.get("messages", [])
    current_draft = state.get("current_draft", "")
    
    prompt = f"""
    You are a writer.
    Current Draft: {current_draft}
    Feedback/Messages: {messages}
    
    Write or revise the draft based on the feedback.
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    
    new_draft = response.text
    return {"current_draft": new_draft, "messages": messages + ["Writer updated draft."]}

def editor_node(state: AgentState) -> dict:
    """
    The Editor node critiques the draft.
    """
    current_draft = state.get("current_draft", "")
    critique_count = state.get("critique_count", 0)
    
    prompt = f"""
    You are an editor.
    Current Draft: {current_draft}
    
    Provide a brief critique of the draft.
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    
    critique = response.text
    return {
        "messages": state.get("messages", []) + [f"Editor critique: {critique}"],
        "critique_count": critique_count + 1
    }

def get_next_step(state: AgentState) -> str:
    """
    Determines the next edge based on the supervisor's decision in the messages.
    Note: In a real supervisor pattern, the supervisor output itself usually drives the edge.
    Here we parse the last message for simplicity or re-run logic.
    However, the prompt asked for the Supervisor to *decide*.
    
    To make this work with LangGraph's conditional edges, we need to extract the decision.
    Let's adjust the supervisor to output a specific key or parse the last message.
    """
    last_message = state["messages"][-1]
    if "Supervisor decided: Writer" in last_message:
        return "writer"
    elif "Supervisor decided: Editor" in last_message:
        return "editor"
    elif "Supervisor decided: FINISH" in last_message:
        return "end"
    return "end"

# Build the Graph
workflow = StateGraph(AgentState)

workflow.add_node("supervisor", supervisor_node)
workflow.add_node("writer", writer_node)
workflow.add_node("editor", editor_node)

# Define edges
workflow.set_entry_point("supervisor")

workflow.add_conditional_edges(
    "supervisor",
    get_next_step,
    {
        "writer": "writer",
        "editor": "editor",
        "end": END
    }
)

workflow.add_edge("writer", "supervisor")
workflow.add_edge("editor", "supervisor")

# Compile the graph
app = workflow.compile()

if __name__ == "__main__":
    # Example usage
    initial_state = {
        "messages": ["Start the process. Topic: The future of AI."],
        "current_draft": "",
        "critique_count": 0
    }
    
    print("Starting workflow...")
    # Iterate through the graph steps
    for output in app.stream(initial_state):
        for key, value in output.items():
            print(f"Node '{key}':")
            # print(value) # Print state updates if needed
            if "current_draft" in value:
                print(f"  Draft length: {len(value['current_draft'])}")
            if "messages" in value:
                print(f"  Last message: {value['messages'][-1]}")
            print("-" * 20)
