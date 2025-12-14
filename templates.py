from __future__ import annotations

from typing import Any, Dict


# ---------- Process template (initial empty document) ----------

PROCESS_TEMPLATE: Dict[str, Any] = {
    "_process_name_instructions": "Short, descriptive name for the process (e.g., 'New Customer Onboarding')",
    "process_name": "",
    "_process_goal_instructions": "What this process aims to achieve - the primary objective",
    "process_goal": "",
    "scope": {
        "_instructions": {
            "start_trigger": "What event or condition initiates this process",
            "end_condition": "What condition marks the completion of this process",
            "in_scope": "What is included in this process",
            "out_of_scope": "What is explicitly excluded from this process"
        },
        "start_trigger": "",
        "end_condition": "",
        "in_scope": [],
        "out_of_scope": [],
    },
    "_actors_instructions": "Extract all people, roles, or personas mentioned in utterances (e.g., 'Sales rep', 'CSM', 'Customer')",
    "actors": [],   # e.g. ["Sales rep", "Customer success", "New customer"]
    "_systems_instructions": "Extract all tools, platforms, or systems mentioned in utterances (e.g., 'HubSpot', 'Slack', 'Gmail')",
    "systems": [],  # e.g. ["HubSpot", "Gmail", "Slack"]
    "_main_flow_instructions": "Array of step objects. Each step should have: id (e.g., 'S1', 'S2'), description (what happens), actor (who performs it), system (what tool/platform is used). Extract sequential steps from utterances.",
    "main_flow": [
        # each step: {"id": "S1", "description": "...", "actor": "", "system": ""}
    ],
    "_exceptions_instructions": "Array of exception objects with condition and action fields. Extract error cases, alternative paths, or conditional logic from utterances.",
    "exceptions": [],
    "_metrics_instructions": "Array of metric objects with name and description. Extract any KPIs, measurements, or success criteria mentioned.",
    "metrics": [],
    "_open_questions_instructions": "Array of strings. Capture any uncertainties, ambiguities, or questions raised in the utterances.",
    "open_questions": [],
}
