"""
Tool wrapper for delegating isolated tasks to specialist Subagents.
"""

from agent.core.subagent_manager import discover_subagents, get_subagent


def delegate_to_subagent(subagent_name: str, task_prompt: str) -> str:
    """
    Delegates a self-contained or context-heavy sub-task to an isolated Subagent.
    The subagent runs with its own ephemeral context window, filtered tools, and resolved model,
    returning only the final synthesized summary.

    Args:
        subagent_name: Identifier of the subagent ('explore', 'git_ops', 'reporter', 'general', or custom name).
        task_prompt: Clear, self-contained instructions and context for the subagent to execute.
    Returns:
        Formatted summary output from the subagent.
    """
    from agent.core.subagent_runner import SubAgentRunner

    if not subagent_name or not str(subagent_name).strip():
        return "Error: 'subagent_name' is required."
    if not task_prompt or not str(task_prompt).strip():
        return "Error: 'task_prompt' is required."

    subagent = get_subagent(subagent_name)
    if not subagent:
        available = ", ".join(s["name"] for s in discover_subagents())
        return f"Error: Subagent '{subagent_name}' not found. Available subagents: {available}"

    try:
        runner = SubAgentRunner(subagent=subagent)
        res = runner.run(task_prompt=str(task_prompt).strip())
        header = (
            f"[Subagent: {res.get('subagent_name')} | "
            f"Model: {res.get('model_used')} | "
            f"Steps: {res.get('steps_taken', 0)} | "
            f"Tool Calls: {res.get('tool_calls_count', 0)}]"
        )
        output = res.get("output", "").strip()
        return f"{header}\n{output}"
    except Exception as e:
        return f"Error executing subagent '{subagent_name}': {e}"
