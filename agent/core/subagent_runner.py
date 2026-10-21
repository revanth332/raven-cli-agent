"""
Isolated Subagent Execution Engine for Raven CLI Agent.
Supports both Mode A (Direct TUI slash-command streaming) and Mode B (Tool-invoked delegation).
"""

import json
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent.core.loop_guard import LoopGuard, LoopGuardState
from agent.core.safety import is_command_dangerous
from agent.core.settings import settings
from agent.core.subagent_manager import (
    detect_git_author,
    get_subagent,
    resolve_subagent_model,
)
from agent.core.token_counter import count_tokens
from agent.core.usage_tracker import UsageTracker


FORBIDDEN_SUBAGENT_TOOLS = {"delegate_to_subagent", "ask_user"}
GATED_SUBAGENT_TOOLS = {"execute_command", "start_background_process", "commit_staged_git_changes"}

_thread_local = threading.local()


def set_subagent_execution_context(
    cancel_event: Optional[threading.Event] = None,
    permission_callback: Optional[Callable[[str, dict], Tuple[bool, str]]] = None,
    status_callback: Optional[Callable[[str], None]] = None,
    usage_tracker: Optional[UsageTracker] = None,
    session_save_callback: Optional[Callable[[], None]] = None,
    active_runner_callback: Optional[Callable[[Optional["SubAgentRunner"]], None]] = None,
    fallback_model: Optional[str] = None,
) -> None:
    """Binds TUI/session callbacks to thread-local storage for tool-invoked subagents."""
    _thread_local.context = {
        "cancel_event": cancel_event,
        "permission_callback": permission_callback,
        "status_callback": status_callback,
        "usage_tracker": usage_tracker,
        "session_save_callback": session_save_callback,
        "active_runner_callback": active_runner_callback,
        "fallback_model": fallback_model,
    }


def clear_subagent_execution_context() -> None:
    """Clears thread-local subagent execution callbacks."""
    _thread_local.context = {}


def get_subagent_execution_context() -> Dict[str, Any]:
    """Retrieves active thread-local subagent execution callbacks."""
    return getattr(_thread_local, "context", {}) or {}


def get_filtered_tools_for_subagent(allowed_tools: List[str]) -> List[Dict[str, Any]]:
    """Returns only the OpenAI tool schema definitions permitted for this subagent."""
    from agent.tools.tool_registry import raven_tools

    allowed_set = {t.strip() for t in (allowed_tools or []) if t.strip()} - FORBIDDEN_SUBAGENT_TOOLS
    if not allowed_set:
        return []

    filtered = []
    for tool_def in raven_tools:
        fn_name = tool_def.get("function", {}).get("name", "")
        if fn_name in allowed_set:
            filtered.append(tool_def)
    return filtered


def format_tool_display_info(tool_name: str, tool_args: dict, tool_meta: dict) -> Tuple[str, str]:
    """Computes human-friendly (display_name, display_val) for a tool call."""
    display_name = "Update" if tool_name == "patch_file" else tool_meta.get("display_name", tool_name)
    arg_keys = tool_meta.get("display_arg")
    display_val = ""
    if tool_name == "patch_file":
        display_val = tool_args.get("file_path", "")
    elif tool_name == "read_file":
        fpath = tool_args.get("file_path", "")
        s_line = tool_args.get("start_line")
        l_count = tool_args.get("line_count")
        if (s_line is not None and int(s_line) > 1) or (l_count is not None and int(l_count) != 250):
            start_val = int(s_line) if s_line else 1
            count_val = int(l_count) if l_count else 250
            end_val = start_val + count_val - 1
            display_val = f"{fpath}:{start_val}-{end_val}"
        else:
            display_val = fpath
    elif isinstance(arg_keys, str):
        display_val = str(tool_args.get(arg_keys, ""))
    elif isinstance(arg_keys, list):
        display_val = ",".join(str(tool_args.get(key, "")) for key in arg_keys)
    return display_name, display_val


class SubAgentRunner:
    """
    Executes a Subagent in an isolated context window with filtered tools,
    bounded LoopGuard turns, and full token/cost accounting.
    """

    def __init__(
        self,
        subagent: Dict[str, Any],
        fallback_model: Optional[str] = None,
        cancel_event: Optional[threading.Event] = None,
        permission_callback: Optional[Callable[[str, dict], Tuple[bool, str]]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        usage_tracker: Optional[UsageTracker] = None,
        session_save_callback: Optional[Callable[[], None]] = None,
    ):
        ctx = get_subagent_execution_context()
        self.subagent = subagent
        self.subagent_name = subagent["name"]
        self.fallback_model = fallback_model or ctx.get("fallback_model") or getattr(settings, "RAVEN_MODEL", "google/gemini-3-flash-preview")
        self.model_name = resolve_subagent_model(subagent, fallback_model=self.fallback_model)
        self.max_steps = int(subagent.get("max_steps", 12))
        self.allowed_tools = [t for t in subagent.get("allowed_tools", []) if t not in FORBIDDEN_SUBAGENT_TOOLS]
        self.tool_schemas = get_filtered_tools_for_subagent(self.allowed_tools)

        self.cancel_event = cancel_event or ctx.get("cancel_event")
        self.permission_callback = permission_callback or ctx.get("permission_callback")
        self.status_callback = status_callback or ctx.get("status_callback")
        self.usage_tracker = usage_tracker or ctx.get("usage_tracker") or UsageTracker()
        self.session_save_callback = session_save_callback or ctx.get("session_save_callback")
        self._active_runner_callback = ctx.get("active_runner_callback")

        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": subagent.get("system_prompt", "")}
        ]
        self._active_stream = None
        self._stream_lock = threading.Lock()
        self._stream_aborted = False

    def _is_cancelled(self) -> bool:
        if self._stream_aborted:
            return True
        if self.cancel_event is not None and self.cancel_event.is_set():
            return True
        return False

    def abort_active_stream(self) -> None:
        """Immediately aborts any in-flight HTTP stream for this subagent."""
        with self._stream_lock:
            self._stream_aborted = True
            stream = self._active_stream
            self._active_stream = None
        if stream is not None:
            try:
                if hasattr(stream, "close"):
                    stream.close()
            except Exception:
                pass
            try:
                inner_resp = getattr(stream, "response", None)
                if inner_resp is not None and hasattr(inner_resp, "close"):
                    inner_resp.close()
            except Exception:
                pass

    def _emit_status(self, message: str) -> None:
        if self.status_callback and not self._is_cancelled():
            try:
                self.status_callback(message)
            except Exception:
                pass

    def _record_usage(
        self,
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
        assistant_text: str,
        duration_ms: float,
        ttft_ms: Optional[float],
        status: str = "success",
        error_code: Optional[str] = None,
    ) -> None:
        try:
            if status == "success":
                if prompt_tokens is None:
                    prompt_tokens = count_tokens(self.messages, self.model_name)
                if completion_tokens is None:
                    completion_tokens = count_tokens(assistant_text or "", self.model_name)
            else:
                prompt_tokens = 0
                completion_tokens = 0

            self.usage_tracker.record_turn(
                prompt_tokens=prompt_tokens or 0,
                completion_tokens=completion_tokens or 0,
                model_name=self.model_name,
                duration_ms=duration_ms,
                ttft_ms=ttft_ms,
                status=status,
                error_code=error_code,
            )
            if self.session_save_callback:
                try:
                    self.session_save_callback()
                except Exception:
                    pass
        except Exception:
            pass

    def run(
        self,
        task_prompt: str,
        on_text_chunk: Optional[Callable[[str], None]] = None,
        on_tool_call: Optional[Callable[[str, str, str, str], None]] = None,
        on_tool_result: Optional[Callable[[str, dict, Any, Optional[str]], None]] = None,
        on_status_block: Optional[Callable[[str, str], None]] = None,
        on_model_fallback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Runs the isolated subagent loop until completion or max_steps.
        Returns a dictionary with:
          - success (bool)
          - output (str)
          - subagent_name (str)
          - model_used (str)
          - steps_taken (int)
          - tool_calls_count (int)
        """
        from agent.core.llm import extract_error_code, get_genai_client
        from agent.tools.tool_registry import TOOL_REGISTRY

        if self._active_runner_callback:
            try:
                self._active_runner_callback(self)
            except Exception:
                pass

        # Enrich reporter prompt with pre-detected git author so it never needs execute_command
        enriched_task = task_prompt
        if self.subagent_name == "reporter":
            git_author = detect_git_author()
            if git_author:
                enriched_task = (
                    f"[Auto-Detected Git Author: {git_author}]\n"
                    f"Use author=\"{git_author}\" directly in `get_git_log`.\n\n"
                    f"{task_prompt}"
                )

        self.messages.append({"role": "user", "content": enriched_task})

        loop_guard = LoopGuard(
            max_turns=self.max_steps,
            hard_max_turns=self.max_steps + 2,
            max_tool_calls=self.max_steps * 3,
            max_no_progress_rounds=2,
            grace_turns=1,
        )

        total_text_response = ""
        steps_taken = 0
        tool_calls_count = 0

        try:
            while True:
                if self._is_cancelled():
                    if on_status_block:
                        on_status_block("Subagent stopped by user.", "bold yellow")
                    return {
                        "success": False,
                        "output": total_text_response or "Subagent execution cancelled by user.",
                        "subagent_name": self.subagent_name,
                        "model_used": self.model_name,
                        "steps_taken": steps_taken,
                        "tool_calls_count": tool_calls_count,
                        "cancelled": True,
                    }

                guard_state = loop_guard.get_state()
                allow_tools = bool(self.tool_schemas)
                execution_instruction = None

                if steps_taken >= self.max_steps or guard_state in (LoopGuardState.WRAP_UP, LoopGuardState.FINALIZE):
                    allow_tools = False
                    execution_instruction = (
                        "You have reached the maximum step budget for this subagent task. "
                        "Do not call any more tools. Synthesize your final response concisely based on the findings gathered so far."
                    )

                request_messages = list(self.messages)
                if execution_instruction:
                    request_messages.append({"role": "system", "content": execution_instruction})

                self._emit_status(f"Subagent [{self.subagent_name}] ({self.model_name}): Thinking...")

                function_calls: Dict[int, Dict[str, Any]] = {}
                round_text = ""
                ttft_ms = None
                server_usage = None
                start_time = time.perf_counter()

                max_retries = 3
                for attempt in range(max_retries):
                    if self._is_cancelled():
                        break
                    function_calls = {}
                    round_text = ""
                    try:
                        request_args: Dict[str, Any] = {
                            "model": self.model_name,
                            "messages": request_messages,
                            "stream": True,
                            "stream_options": {"include_usage": True},
                        }
                        if allow_tools and self.tool_schemas:
                            request_args["tools"] = self.tool_schemas

                        client = get_genai_client()
                        try:
                            response = client.chat.completions.create(**request_args)
                        except Exception as inner_err:
                            if "stream_options" in str(inner_err).lower():
                                request_args.pop("stream_options", None)
                                response = client.chat.completions.create(**request_args)
                            else:
                                raise inner_err

                        with self._stream_lock:
                            if self._is_cancelled():
                                try:
                                    if hasattr(response, "close"):
                                        response.close()
                                except Exception:
                                    pass
                                break
                            self._active_stream = response

                        try:
                            for chunk in response:
                                if self._is_cancelled():
                                    break
                                if ttft_ms is None:
                                    ttft_ms = (time.perf_counter() - start_time) * 1000.0

                                usage = getattr(chunk, "usage", None)
                                if usage is not None:
                                    p_tok = getattr(usage, "prompt_tokens", None)
                                    c_tok = getattr(usage, "completion_tokens", None)
                                    if isinstance(usage, dict):
                                        p_tok = usage.get("prompt_tokens")
                                        c_tok = usage.get("completion_tokens")
                                    if p_tok is not None or c_tok is not None:
                                        server_usage = {"prompt_tokens": p_tok, "completion_tokens": c_tok}

                                if not getattr(chunk, "choices", None):
                                    continue
                                delta = chunk.choices[0].delta
                                if hasattr(delta, "tool_calls") and delta.tool_calls:
                                    for tc in delta.tool_calls:
                                        idx = tc.index
                                        if idx not in function_calls:
                                            function_calls[idx] = {"id": "", "name": "", "arguments": ""}
                                        if tc.id:
                                            function_calls[idx]["id"] = tc.id
                                        if tc.function and tc.function.name:
                                            function_calls[idx]["name"] += tc.function.name
                                        if tc.function and tc.function.arguments:
                                            function_calls[idx]["arguments"] += tc.function.arguments
                                        if getattr(tc, "extra_content", None):
                                            function_calls[idx]["extra_content"] = tc.extra_content

                                if hasattr(delta, "content") and delta.content:
                                    round_text += delta.content
                                    if on_text_chunk:
                                        on_text_chunk(delta.content)
                        finally:
                            with self._stream_lock:
                                if self._active_stream is response:
                                    self._active_stream = None
                            try:
                                if hasattr(response, "close"):
                                    response.close()
                            except Exception:
                                pass

                        duration_ms = (time.perf_counter() - start_time) * 1000.0
                        p_tokens = server_usage.get("prompt_tokens") if server_usage else None
                        c_tokens = server_usage.get("completion_tokens") if server_usage else None
                        self._record_usage(
                            prompt_tokens=p_tokens,
                            completion_tokens=c_tokens,
                            assistant_text=round_text,
                            duration_ms=duration_ms,
                            ttft_ms=ttft_ms,
                            status="success",
                        )
                        break

                    except Exception as api_err:
                        duration_ms = (time.perf_counter() - start_time) * 1000.0
                        if self._is_cancelled():
                            break
                        err_lower = str(api_err).lower()
                        # Automatic fallback to primary model if configured SMALL_MODEL is invalid/unsupported
                        if (
                            self.model_name != self.fallback_model
                            and self.fallback_model
                            and any(k in err_lower for k in ("not found", "404", "invalid model", "does not exist", "model_not_found", "400"))
                        ):
                            self._record_usage(0, 0, "", duration_ms, None, status="error", error_code=extract_error_code(api_err))
                            self.model_name = self.fallback_model
                            if on_model_fallback:
                                try:
                                    on_model_fallback(self.model_name)
                                except Exception:
                                    pass
                            continue

                        if attempt < max_retries - 1 and any(k in err_lower for k in ("429", "rate", "quota", "503", "502", "timeout", "connection")):
                            sleep_s = 2 ** (attempt + 1)
                            if self.cancel_event and self.cancel_event.wait(timeout=sleep_s):
                                break
                            continue

                        self._record_usage(0, 0, "", duration_ms, None, status="error", error_code=extract_error_code(api_err))
                        raise api_err

                if self._is_cancelled():
                    if on_status_block:
                        on_status_block("Subagent stopped by user.", "bold yellow")
                    return {
                        "success": False,
                        "output": total_text_response or round_text or "Subagent execution cancelled by user.",
                        "subagent_name": self.subagent_name,
                        "model_used": self.model_name,
                        "steps_taken": steps_taken,
                        "tool_calls_count": tool_calls_count,
                        "cancelled": True,
                    }

                if round_text:
                    if total_text_response:
                        total_text_response += "\n\n" + round_text
                    else:
                        total_text_response = round_text

                if round_text or function_calls:
                    assistant_msg: Dict[str, Any] = {"role": "assistant"}
                    if round_text:
                        assistant_msg["content"] = round_text
                    if function_calls:
                        tc_list = []
                        for _, fc in function_calls.items():
                            tc_item: Dict[str, Any] = {
                                "id": fc["id"] or f"call_{steps_taken}_{fc['name']}",
                                "type": "function",
                                "function": {
                                    "name": fc["name"],
                                    "arguments": fc["arguments"] or "{}",
                                },
                            }
                            if fc.get("extra_content"):
                                tc_item["extra_content"] = fc["extra_content"]
                            tc_list.append(tc_item)
                        assistant_msg["tool_calls"] = tc_list
                    self.messages.append(assistant_msg)

                if not function_calls or not allow_tools:
                    break

                steps_taken += 1
                loop_guard.increment_turn()
                round_made_progress = False

                for _, fc in function_calls.items():
                    if self._is_cancelled():
                        break

                    tool_name = fc["name"]
                    tool_call_id = fc["id"] or f"call_{steps_taken}_{tool_name}"
                    loop_guard.record_tool_call()
                    tool_calls_count += 1

                    try:
                        tool_args = json.loads(fc["arguments"]) if fc["arguments"] else {}
                    except Exception as parse_err:
                        err_msg = f"Error parsing tool arguments: {parse_err}"
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": tool_name,
                            "content": err_msg,
                        })
                        continue

                    # Enforce whitelist security boundary
                    if tool_name not in self.allowed_tools or tool_name in FORBIDDEN_SUBAGENT_TOOLS or tool_name not in TOOL_REGISTRY:
                        denied_msg = f"Error: Tool '{tool_name}' is not permitted for subagent '{self.subagent_name}'."
                        if on_tool_call:
                            on_tool_call(tool_name, tool_name, "Not Permitted", "denied")
                        if on_tool_result:
                            on_tool_result(tool_name, tool_args, denied_msg, "denied")
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": tool_name,
                            "content": denied_msg,
                        })
                        continue

                    # Duplicate tool call guard
                    is_dup, dup_msg = loop_guard.check_duplicate(tool_name, tool_args)
                    if is_dup:
                        if on_tool_call:
                            on_tool_call(tool_name, "Duplicate Intercepted", tool_name, "completed")
                        if on_tool_result:
                            on_tool_result(tool_name, tool_args, dup_msg, "duplicate")
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": tool_name,
                            "content": json.dumps(dup_msg),
                        })
                        continue

                    loop_guard.record_call(tool_name, tool_args)
                    tool_meta = TOOL_REGISTRY[tool_name]
                    display_name, display_val = format_tool_display_info(tool_name, tool_args, tool_meta)

                    # Permission gating for sensitive tools
                    if tool_name in GATED_SUBAGENT_TOOLS:
                        bypass_prompt = False
                        if settings.RAVEN_AUTO_APPROVE:
                            if tool_name == "commit_staged_git_changes":
                                bypass_prompt = True
                            elif tool_name in ("execute_command", "start_background_process"):
                                cmd_str = tool_args.get("command", "")
                                if not is_command_dangerous(cmd_str):
                                    bypass_prompt = True

                        if not bypass_prompt:
                            if self.permission_callback:
                                allowed, instr = self.permission_callback(tool_name, tool_args)
                                if self._is_cancelled():
                                    break
                                if not allowed:
                                    if instr:
                                        result = f"User denied permission and provided instructions: '{instr}'"
                                    else:
                                        result = "Error: User denied permission."
                                    if on_tool_call:
                                        on_tool_call(tool_name, display_name, display_val, "denied")
                                    if on_tool_result:
                                        on_tool_result(tool_name, tool_args, result, "denied")
                                    self.messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call_id,
                                        "name": tool_name,
                                        "content": result,
                                    })
                                    continue
                            else:
                                # Headless fallback without permission_callback: deny dangerous commands
                                result = f"Error: Tool '{tool_name}' requires user permission, which is unavailable in headless mode."
                                self.messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call_id,
                                    "name": tool_name,
                                    "content": result,
                                })
                                continue

                    if on_tool_call:
                        on_tool_call(tool_name, display_name, display_val, "running")

                    self._emit_status(f"Subagent [{self.subagent_name}]: Executing {display_name}...")

                    try:
                        result = tool_meta["fn"](**tool_args)
                    except Exception as exec_err:
                        result = f"Error: {exec_err}"

                    if self._is_cancelled():
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": tool_name,
                            "content": json.dumps(str(result) if result else "Tool execution cancelled by user."),
                        })
                        break

                    if on_tool_result:
                        on_tool_result(tool_name, tool_args, result, "completed")

                    if loop_guard.result_made_progress(result):
                        round_made_progress = True

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": json.dumps(result),
                    })

                loop_guard.record_round_outcome(round_made_progress)

            return {
                "success": True,
                "output": total_text_response.strip() or "Subagent task completed.",
                "subagent_name": self.subagent_name,
                "model_used": self.model_name,
                "steps_taken": steps_taken,
                "tool_calls_count": tool_calls_count,
            }
        finally:
            if self._active_runner_callback:
                try:
                    self._active_runner_callback(None)
                except Exception:
                    pass
