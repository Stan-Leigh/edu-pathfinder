# ruff: noqa
import datetime
import json
import logging
import re
import sys
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.apps import App, ResumabilityConfig
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.tools import AgentTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.workflow import Workflow, START
from google.genai import types
from mcp import StdioServerParameters

from .config import config

# Configure audit logging
logger = logging.getLogger("edu_pathfinder_audit")
logger.setLevel(logging.INFO)
# Standard output logging
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Setup MCP Toolset to execute mcp_server.py
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_server"],
        )
    )
)

# 1. Specialized Sub-Agents
curriculum_agent = LlmAgent(
    name="curriculum_agent",
    model=config.model,
    instruction="""You are a Curriculum and Study Plan Specialist.
Your task is to analyze the student's learning goals and subject, and generate a structured, step-by-step personalized curriculum.
Utilize the 'get_study_resources' tool to find actual open-source study guides and textbooks, and log intermediate progress using 'log_study_progress' if requested.
Always focus on accessible, free educational materials.
""",
    tools=[mcp_toolset],
    description="Creates personalized curriculums and retrieves study resources for specific topics.",
)

tutor_match_agent = LlmAgent(
    name="tutor_match_agent",
    model=config.model,
    instruction="""You are a Peer Tutoring and Mentorship Specialist.
Your task is to help students find suitable, free academic support.
Utilize the 'get_tutors_by_subject' tool to lookup matching tutors, peer study groups, and free support desks.
Provide clear details including tutor name, rating, availability, and how to connect.
""",
    tools=[mcp_toolset],
    description="Finds available free tutors, mentoring programs, and peer study groups for a given subject.",
)

# 2. Main Orchestrator Agent
edu_orchestrator = LlmAgent(
    name="edu_orchestrator",
    model=config.model,
    instruction="""You are the main coordinator for Edu-Pathfinder.
Your goal is to guide students on their educational journey by acting as a single point of contact.
Use 'AgentTool' to delegate tasks to specialized sub-agents:
- For curriculum design and study resources, call 'curriculum_agent'.
- For finding tutors, mentoring circles, and free help, call 'tutor_match_agent'.

Assemble their responses into a single cohesive, highly professional education path recommendation.
State clearly what resources they have and what tutors they can contact.
""",
    tools=[AgentTool(curriculum_agent), AgentTool(tutor_match_agent)],
    output_key="orchestrator_output",
)

# Helper function to extract query/text from any input type
def extract_text(node_input: Any) -> str:
    if isinstance(node_input, str):
        return node_input
    if isinstance(node_input, dict):
        return node_input.get("query", "")
    if hasattr(node_input, "query"):
        return node_input.query
    if hasattr(node_input, "parts") and node_input.parts:
        return "".join(part.text for part in node_input.parts if part.text)
    return str(node_input)

# 3. Workflow Function Nodes
def security_checkpoint(ctx: Context, node_input: Any):
    """Workflow entry checkpoint validating safety, prompt injection, and PII."""
    query_text = extract_text(node_input)
    
    # PII scrubbing (phone, email, student ID)
    scrubbed_text = query_text
    scrubbed_text = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[REDACTED_PHONE]", scrubbed_text)
    scrubbed_text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[REDACTED_EMAIL]", scrubbed_text)
    scrubbed_text = re.sub(r"\b(SID|ID|sid|id)[-._]?\d{5,8}\b", "[REDACTED_STUDENT_ID]", scrubbed_text)
    
    pii_detected = scrubbed_text != query_text
    
    # Prompt injection detection
    injection_keywords = ["ignore previous instructions", "system prompt", "override instructions", "you are now an evil", "dan mode"]
    injection_detected = any(kw in query_text.lower() for kw in injection_keywords)
    
    # Domain-specific rule: Underage safety / consent check
    underage_keywords = ["i am 10", "i am 11", "i am 12", "i'm 10", "i'm 11", "i'm 12", "i am under 13"]
    consent_needed = any(kw in query_text.lower() for kw in underage_keywords)
    
    audit_data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "session_id": ctx.session.id,
        "pii_detected": pii_detected,
        "injection_detected": injection_detected,
        "consent_needed": consent_needed,
        "original_query_length": len(query_text)
    }
    
    if injection_detected:
        audit_data["severity"] = "CRITICAL"
        audit_data["action"] = "BLOCKED"
        logger.warning(json.dumps(audit_data))
        return Event(
            output="Security Violation: Potential prompt injection detected. Access Denied.",
            route="security_event"
        )
    elif consent_needed:
        audit_data["severity"] = "WARNING"
        audit_data["action"] = "FLAGGED_FOR_CONSENT"
        logger.warning(json.dumps(audit_data))
        return Event(
            output="Safety Notification: Parent or guardian consent is required for users under 13 years of age. Please ask a parent or teacher to verify your account.",
            route="security_event"
        )
    else:
        audit_data["severity"] = "INFO"
        audit_data["action"] = "PASSED"
        logger.info(json.dumps(audit_data))
        return Event(
            output=scrubbed_text,
            state={"query": scrubbed_text}
        )

def security_event_handler(node_input: str):
    """Outputs the security warning when an incident occurs."""
    yield Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=node_input)]
        ),
        output=node_input
    )

async def human_approval(ctx: Context, node_input: Any):
    """Asks the student/teacher for approval of the generated plan."""
    if not ctx.resume_inputs:
        plan_text = extract_text(node_input)
        yield RequestInput(
            interrupt_id="approve_plan",
            message=f"### Proposed Plan and Matchings:\n\n{plan_text}\n\nDo you approve this study path? (yes/no)"
        )
        return
    
    user_response = ctx.resume_inputs.get("approve_plan", "")
    if str(user_response).lower().strip() in ["yes", "approve", "y"]:
        ctx.state["approval_status"] = "APPROVED"
        yield Event(output=node_input, route="approved")
    else:
        ctx.state["approval_status"] = "REJECTED"
        yield Event(output="Plan rejected. Adjusting constraints...", route="rejected")

def final_output(ctx: Context, node_input: Any):
    """Processes approved recommendations and renders final dashboard confirmation."""
    plan_text = extract_text(node_input)
    ctx.state["finalized_plan"] = plan_text
    
    final_message = (
        f"### 🎉 Educational Plan Finalized & Approved!\n\n"
        f"{plan_text}\n\n"
        f"*Status: Student dashboard and study progress tracking are now active.*"
    )
    yield Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=final_message)]
        ),
        output=plan_text
    )

# 4. Workflow Graph Construction
root_agent = Workflow(
    name="edu_workflow",
    edges=[
        (START, security_checkpoint),
        (security_checkpoint, {
            "security_event": security_event_handler,
            "__DEFAULT__": edu_orchestrator,
        }),
        (edu_orchestrator, human_approval),
        (human_approval, {
            "approved": final_output,
            "rejected": edu_orchestrator,
        }),
    ]
)

app = App(
    root_agent=root_agent,
    name="app",
    resumability_config=ResumabilityConfig(is_resumable=True)
)
