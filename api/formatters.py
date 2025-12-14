from __future__ import annotations

from typing import Dict, Any, List


def format_document(doc: Dict[str, Any]) -> str:
    """
    Convert JSON document state to nicely formatted readable text.
    
    Args:
        doc: Document state dictionary from DocumentUpdater
        
    Returns:
        Formatted text representation
    """
    lines = []
    
    # Process name and goal
    process_name = doc.get("process_name", "").strip()
    if process_name:
        lines.append(f"# {process_name}")
        lines.append("")
    
    process_goal = doc.get("process_goal", "").strip()
    if process_goal:
        lines.append(f"**Goal:** {process_goal}")
        lines.append("")
    
    # Scope
    scope = doc.get("scope", {})
    if scope:
        start_trigger = scope.get("start_trigger", "").strip()
        end_condition = scope.get("end_condition", "").strip()
        in_scope = scope.get("in_scope", [])
        out_of_scope = scope.get("out_of_scope", [])
        
        # Only show scope section if there's actual content
        if start_trigger or end_condition or in_scope or out_of_scope:
            lines.append("## Scope")
            
            if start_trigger:
                lines.append(f"**Start Trigger:** {start_trigger}")
            
            if end_condition:
                lines.append(f"**End Condition:** {end_condition}")
            
            if in_scope:
                lines.append("**In Scope:**")
                for item in in_scope:
                    if isinstance(item, str) and item.strip():
                        lines.append(f"  - {item}")
            
            if out_of_scope:
                lines.append("**Out of Scope:**")
                for item in out_of_scope:
                    if isinstance(item, str) and item.strip():
                        lines.append(f"  - {item}")
            
            lines.append("")
    
    # Actors
    actors = doc.get("actors", [])
    if actors:
        lines.append("## Actors")
        for actor in actors:
            if isinstance(actor, str) and actor.strip():
                lines.append(f"  - {actor}")
        lines.append("")
    
    # Systems
    systems = doc.get("systems", [])
    if systems:
        lines.append("## Systems")
        for system in systems:
            if isinstance(system, str) and system.strip():
                lines.append(f"  - {system}")
        lines.append("")
    
    # Main flow
    main_flow = doc.get("main_flow", [])
    if main_flow:
        # Check if there's actual content to display
        has_content = False
        for step in main_flow:
            if isinstance(step, dict):
                if step.get("description", "").strip():
                    has_content = True
                    break
            elif isinstance(step, str) and step.strip():
                has_content = True
                break
        
        if has_content:
            lines.append("## Main Flow")
            for i, step in enumerate(main_flow, 1):
                if isinstance(step, dict):
                    step_id = step.get("id", f"S{i}")
                    description = step.get("description", "").strip()
                    actor = step.get("actor", "").strip()
                    system = step.get("system", "").strip()
                    
                    if description:
                        step_line = f"{step_id}. {description}"
                        if actor:
                            step_line += f" (Actor: {actor})"
                        if system:
                            step_line += f" (System: {system})"
                        lines.append(step_line)
                elif isinstance(step, str) and step.strip():
                    # Handle string items in main_flow
                    lines.append(f"{i}. {step}")
            lines.append("")
    
    # Exceptions
    exceptions = doc.get("exceptions", [])
    if exceptions:
        lines.append("## Exceptions")
        for i, exception in enumerate(exceptions, 1):
            if isinstance(exception, dict):
                condition = exception.get("condition", "").strip()
                action = exception.get("action", "").strip()
                if condition or action:
                    exc_line = f"{i}. "
                    if condition:
                        exc_line += f"**{condition}**: "
                    if action:
                        exc_line += action
                    lines.append(exc_line)
            elif isinstance(exception, str) and exception.strip():
                lines.append(f"  - {exception}")
        lines.append("")
    
    # Metrics
    metrics = doc.get("metrics", [])
    if metrics:
        lines.append("## Metrics")
        for metric in metrics:
            if isinstance(metric, dict):
                name = metric.get("name", "").strip()
                description = metric.get("description", "").strip()
                if name:
                    metric_line = f"  - **{name}**"
                    if description:
                        metric_line += f": {description}"
                    lines.append(metric_line)
            elif isinstance(metric, str) and metric.strip():
                lines.append(f"  - {metric}")
        lines.append("")
    
    # Open questions
    open_questions = doc.get("open_questions", [])
    if open_questions:
        lines.append("## Open Questions")
        for question in open_questions:
            if isinstance(question, str) and question.strip():
                lines.append(f"  - {question}")
        lines.append("")
    
    # If document is empty, show placeholder
    if not lines or (len(lines) == 1 and not lines[0]):
        return "No document content yet. Start processing utterances to build the document."
    
    return "\n".join(lines)

