"""
Deterministic Session Transcript Export Engine (/export).
Serializes active chat conversations into sanitized Markdown (.md), JSON (.json),
or standalone HTML (.html) artifacts with collapsible tool traces and Base64 stripping.
"""

from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict

from agent.core.session_manager import load_session
from agent.core.settings import settings
from agent.tools.miscellaneous_tools import strip_ansi
from agent.tools.tool_registry import TOOL_REGISTRY
from agent.utils import get_active_project_name

ExportFormat = Literal["md", "json", "html"]

_DATA_URI_RE = re.compile(
    r"^data:(?P<mime>[a-zA-Z0-9.+/-]+);base64,(?P<b64>[A-Za-z0-9+/=\s]+)$",
    re.DOTALL,
)
_ILLEGAL_WIN_CHARS_RE = re.compile(r'[<>:"|?*\x00-\x1f]')


class SanitizedAttachment(TypedDict):
    media_type: str
    approx_bytes: int
    sha256_prefix: str


class ToolExecutionTrace(TypedDict):
    call_id: str
    tool_name: str
    display_label: str
    arguments: Dict[str, Any]
    result_content: str
    is_error: bool


class TranscriptTurn(TypedDict):
    turn_index: int
    role: Literal["user", "assistant"]
    model_name: Optional[str]
    timestamp: Optional[str]
    text_content: str
    attachments: List[SanitizedAttachment]
    tool_traces: List[ToolExecutionTrace]


class SessionExportEnvelope(TypedDict):
    schema_version: Literal["1.0"]
    session_id: str
    parent_session_id: Optional[str]
    title: str
    project_name: str
    model_name: str
    created_at: str
    exported_at: str
    metrics: Dict[str, Any]
    turns: List[TranscriptTurn]


def slugify_title(title: str, max_len: int = 40) -> str:
    """Converts a session title into a filesystem-safe lowercase slug."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    if not cleaned:
        return "untitled"
    return cleaned[:max_len].rstrip("-") or "untitled"


def format_byte_size(num_bytes: int) -> str:
    """Formats a byte count into a compact human-readable string."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    kb = num_bytes / 1024.0
    if kb < 1024:
        return f"{kb:.1f} KB"
    mb = kb / 1024.0
    return f"{mb:.2f} MB"


def _safe_code_fence(content: str, min_len: int = 3) -> str:
    """Returns a backtick fence string longer than any backtick sequence in content."""
    matches = re.findall(r"`+", content or "")
    max_found = max((len(m) for m in matches), default=0)
    return "`" * max(min_len, max_found + 1)


def _escape_details_tag(text: str) -> str:
    """Prevents raw </details> tags inside tool outputs from prematurely closing collapsible blocks."""
    return re.sub(r"</details>", "&lt;/details&gt;", text or "", flags=re.IGNORECASE)


def _format_tool_display_label(tool_name: str, tool_args: Dict[str, Any]) -> str:
    """Builds a concise human-readable summary label for a tool call."""
    tool_meta = TOOL_REGISTRY.get(tool_name, {})
    disp_name = "Update" if tool_name == "patch_file" else tool_meta.get("display_name", tool_name)
    arg_keys = tool_meta.get("display_arg")
    disp_val = ""

    if not isinstance(tool_args, dict):
        tool_args = {}

    if tool_name == "patch_file":
        disp_val = str(tool_args.get("file_path", ""))
    elif tool_name == "read_file":
        fpath = str(tool_args.get("file_path", ""))
        s_line = tool_args.get("start_line")
        l_count = tool_args.get("line_count")
        try:
            if (s_line is not None and int(s_line) > 1) or (l_count is not None and int(l_count) != 250):
                start_val = int(s_line) if s_line else 1
                count_val = int(l_count) if l_count else 250
                end_val = start_val + count_val - 1
                disp_val = f"{fpath}:{start_val}-{end_val}"
            else:
                disp_val = fpath
        except Exception:
            disp_val = fpath
    elif isinstance(arg_keys, str) and arg_keys:
        disp_val = str(tool_args.get(arg_keys, ""))
    elif isinstance(arg_keys, list):
        disp_val = ", ".join(str(tool_args.get(k, "")) for k in arg_keys if tool_args.get(k) is not None)

    disp_val = disp_val.strip()
    if len(disp_val) > 90:
        disp_val = disp_val[:87] + "..."
    return f"{disp_name}: {disp_val}" if disp_val else disp_name


def _sanitize_data_uri(url_str: str) -> SanitizedAttachment:
    """Extracts media type, approximate decoded size, and SHA-256 prefix from an image URL or Data URI."""
    raw = (url_str or "").strip()
    match = _DATA_URI_RE.match(raw)
    if match:
        mime = match.group("mime") or "image/png"
        b64_clean = re.sub(r"\s+", "", match.group("b64") or "")
        padding = b64_clean.count("=")
        approx_bytes = max(0, (len(b64_clean) * 3) // 4 - padding)
        sha_prefix = hashlib.sha256(b64_clean.encode("utf-8", errors="ignore")).hexdigest()[:12]
        return {
            "media_type": mime,
            "approx_bytes": approx_bytes,
            "sha256_prefix": sha_prefix,
        }

    sha_prefix = hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return {
        "media_type": "image/external",
        "approx_bytes": len(raw),
        "sha256_prefix": sha_prefix,
    }


def _sanitize_arbitrary_value(val: Any) -> Any:
    """Recursively strips inline Base64 data URIs from arbitrary dicts/lists/strings."""
    if isinstance(val, str):
        if val.startswith("data:image/") and ";base64," in val and len(val) > 256:
            att = _sanitize_data_uri(val)
            return (
                f"[Attached Image: {att['media_type']}, "
                f"~{format_byte_size(att['approx_bytes'])}, sha256:{att['sha256_prefix']}]"
            )
        return val
    if isinstance(val, list):
        return [_sanitize_arbitrary_value(item) for item in val]
    if isinstance(val, dict):
        return {k: _sanitize_arbitrary_value(v) for k, v in val.items()}
    return val


def resolve_export_target(
    raw_path_arg: str,
    session_id: str,
    title: str,
    workspace_dir: Optional[Path] = None,
) -> Tuple[Path, ExportFormat]:
    """
    Resolves the output file path and target format (.md, .json, .html)
    according to the CLI path routing specification.
    """
    base_dir = (workspace_dir or Path.cwd()).resolve()
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(session_id or "active")) or "active"
    slug = slugify_title(title)
    default_filename = f"raven-session-{safe_id}-{slug}.md"

    cleaned_arg = (raw_path_arg or "").strip().strip('"').strip("'")
    if not cleaned_arg:
        return (base_dir / default_filename).resolve(), "md"

    expanded = os.path.expanduser(cleaned_arg)
    is_explicit_dir = expanded.endswith(("/", "\\"))

    candidate = Path(expanded)
    if not candidate.is_absolute():
        candidate = base_dir / candidate

    if is_explicit_dir or (candidate.exists() and candidate.is_dir()):
        target_path = candidate / default_filename
        return target_path.resolve(), "md"

    # Validate filename component for illegal Windows characters
    safe_name = _ILLEGAL_WIN_CHARS_RE.sub("-", candidate.name).strip()
    if not safe_name:
        safe_name = default_filename
    candidate = candidate.parent / safe_name

    suffix = candidate.suffix.lower()
    if suffix == ".json":
        return candidate.resolve(), "json"
    if suffix in (".html", ".htm"):
        return candidate.resolve(), "html"
    if suffix in (".md", ".markdown"):
        return candidate.resolve(), "md"
    if not suffix:
        candidate = candidate.with_suffix(".md")
        return candidate.resolve(), "md"

    return candidate.resolve(), "md"


def build_export_envelope(
    session_data: Dict[str, Any],
    max_tool_output_chars: int = 10_000,
    truncate_tool_output: bool = True,
) -> SessionExportEnvelope:
    """
    Normalizes raw session messages and metadata into a sanitized SessionExportEnvelope AST.
    Pairs assistant tool_calls with tool role outputs and strips inline Base64 blobs.
    """
    session_id = str(session_data.get("session_id") or "local")
    persisted = load_session(session_id) if session_id and session_id != "local" else None

    title = str(
        session_data.get("title")
        or (persisted.get("title") if persisted else None)
        or "Untitled Conversation"
    )
    model_name = str(
        session_data.get("model_name")
        or (persisted.get("model_name") if persisted else None)
        or settings.RAVEN_MODEL
    )
    project_name = str(
        session_data.get("project_name")
        or (persisted.get("project_name") if persisted else None)
        or get_active_project_name()
        or Path.cwd().name
    )
    parent_session_id = (
        session_data.get("parent_session_id")
        or (persisted.get("parent_session_id") if persisted else None)
    )

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    created_at = str(
        session_data.get("created_at")
        or (persisted.get("created_at") if persisted else None)
        or now_iso
    )

    prompt_tokens = int(
        session_data.get(
            "session_prompt_tokens",
            persisted.get("session_prompt_tokens", 0) if persisted else 0,
        )
        or 0
    )
    completion_tokens = int(
        session_data.get(
            "session_completion_tokens",
            persisted.get("session_completion_tokens", 0) if persisted else 0,
        )
        or 0
    )
    total_tokens = int(
        session_data.get("total_tokens")
        or (prompt_tokens + completion_tokens)
    )
    session_cost = float(
        session_data.get(
            "session_cost",
            persisted.get("session_cost", 0.0) if persisted else 0.0,
        )
        or 0.0
    )
    session_requests = int(
        session_data.get(
            "session_requests",
            persisted.get("session_requests", 0) if persisted else 0,
        )
        or 0
    )

    raw_messages: List[Dict[str, Any]] = list(session_data.get("messages") or [])
    turns: List[TranscriptTurn] = []
    turn_idx = 0
    i = 0
    n = len(raw_messages)

    while i < n:
        msg = raw_messages[i]
        if not isinstance(msg, dict):
            i += 1
            continue

        role = msg.get("role")
        content = msg.get("content")

        if role == "system":
            i += 1
            continue

        if role == "user":
            attachments: List[SanitizedAttachment] = []
            text_parts: List[str] = []

            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    ptype = part.get("type")
                    if ptype == "text":
                        txt = str(part.get("text") or "").strip()
                        if txt:
                            text_parts.append(txt)
                    elif ptype == "image_url":
                        img_obj = part.get("image_url")
                        url_val = img_obj.get("url", "") if isinstance(img_obj, dict) else str(img_obj or "")
                        if url_val:
                            attachments.append(_sanitize_data_uri(url_val))
            elif content is not None:
                txt = str(content).strip()
                if txt:
                    text_parts.append(txt)

            if text_parts or attachments:
                turn_idx += 1
                turns.append(
                    {
                        "turn_index": turn_idx,
                        "role": "user",
                        "model_name": None,
                        "timestamp": msg.get("timestamp"),
                        "text_content": "\n\n".join(text_parts),
                        "attachments": attachments,
                        "tool_traces": [],
                    }
                )
            i += 1
            continue

        if role in ("assistant", "tool"):
            assistant_texts: List[str] = []
            tool_traces: List[ToolExecutionTrace] = []
            trace_by_id: Dict[str, ToolExecutionTrace] = {}
            unmatched_by_name: Dict[str, List[ToolExecutionTrace]] = {}
            turn_model: Optional[str] = None
            turn_timestamp: Optional[str] = msg.get("timestamp")

            while i < n and isinstance(raw_messages[i], dict) and raw_messages[i].get("role") in ("assistant", "tool"):
                sub_msg = raw_messages[i]
                sub_role = sub_msg.get("role")
                sub_content = sub_msg.get("content")

                if sub_role == "assistant":
                    if not turn_model and sub_msg.get("model_name"):
                        turn_model = str(sub_msg.get("model_name"))
                    if sub_content:
                        cleaned_sub = str(sub_content).strip()
                        if cleaned_sub:
                            assistant_texts.append(cleaned_sub)

                    tool_calls = sub_msg.get("tool_calls") or []
                    for tc_idx, tc in enumerate(tool_calls):
                        if not isinstance(tc, dict):
                            continue
                        tc_id = str(tc.get("id") or f"call_{turn_idx + 1}_{tc_idx + 1}")
                        fn = tc.get("function") or {}
                        t_name = str(fn.get("name") or "unknown_tool")
                        raw_args = fn.get("arguments", "{}")
                        try:
                            parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                            if not isinstance(parsed_args, dict):
                                parsed_args = {"value": parsed_args}
                        except Exception:
                            parsed_args = {"_raw_arguments": str(raw_args)}

                        sanitized_args = _sanitize_arbitrary_value(parsed_args)
                        disp_label = _format_tool_display_label(t_name, sanitized_args)

                        trace_entry: ToolExecutionTrace = {
                            "call_id": tc_id,
                            "tool_name": t_name,
                            "display_label": disp_label,
                            "arguments": sanitized_args,
                            "result_content": "[Interrupted / No tool output recorded]",
                            "is_error": True,
                        }
                        tool_traces.append(trace_entry)
                        trace_by_id[tc_id] = trace_entry
                        unmatched_by_name.setdefault(t_name, []).append(trace_entry)

                elif sub_role == "tool":
                    t_name = str(sub_msg.get("name") or "tool")
                    tc_id = str(sub_msg.get("tool_call_id") or "")
                    raw_res = sub_msg.get("content", "")
                    if isinstance(raw_res, (dict, list)):
                        res_str = json.dumps(_sanitize_arbitrary_value(raw_res), indent=2, ensure_ascii=False)
                    else:
                        res_str = str(_sanitize_arbitrary_value(raw_res or ""))

                    clean_res = strip_ansi(res_str).strip()
                    is_err = bool(
                        clean_res.lower().startswith(("error:", "failed", "exception:"))
                        or '"error":' in clean_res.lower()
                    )

                    if truncate_tool_output and max_tool_output_chars > 0 and len(clean_res) > max_tool_output_chars:
                        omitted = len(clean_res) - max_tool_output_chars
                        clean_res = f"{clean_res[:max_tool_output_chars]}\n... [truncated {omitted:,} chars]"

                    matched_trace: Optional[ToolExecutionTrace] = None
                    if tc_id and tc_id in trace_by_id:
                        matched_trace = trace_by_id[tc_id]
                        queue = unmatched_by_name.get(matched_trace["tool_name"], [])
                        if matched_trace in queue:
                            queue.remove(matched_trace)
                    elif unmatched_by_name.get(t_name):
                        matched_trace = unmatched_by_name[t_name].pop(0)

                    if matched_trace is not None:
                        matched_trace["result_content"] = clean_res or "(Empty output)"
                        matched_trace["is_error"] = is_err
                    else:
                        orphan_id = tc_id or f"orphan_{len(tool_traces) + 1}"
                        tool_traces.append(
                            {
                                "call_id": orphan_id,
                                "tool_name": t_name,
                                "display_label": _format_tool_display_label(t_name, {}),
                                "arguments": {},
                                "result_content": clean_res or "(Empty output)",
                                "is_error": is_err,
                            }
                        )

                i += 1

            if assistant_texts or tool_traces:
                turn_idx += 1
                turns.append(
                    {
                        "turn_index": turn_idx,
                        "role": "assistant",
                        "model_name": turn_model or model_name,
                        "timestamp": turn_timestamp,
                        "text_content": "\n\n".join(assistant_texts),
                        "attachments": [],
                        "tool_traces": tool_traces,
                    }
                )
            continue

        i += 1

    return {
        "schema_version": "1.0",
        "session_id": session_id,
        "parent_session_id": parent_session_id,
        "title": title,
        "project_name": project_name,
        "model_name": model_name,
        "created_at": created_at,
        "exported_at": now_iso,
        "metrics": {
            "turn_count": len(turns),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "session_cost_usd": round(session_cost, 6),
            "session_requests": session_requests,
        },
        "turns": turns,
    }


def render_markdown_export(envelope: SessionExportEnvelope) -> str:
    """Renders the normalized SessionExportEnvelope into GitHub-Flavored Markdown."""
    metrics = envelope["metrics"]
    safe_yaml_title = envelope["title"].replace('"', '\\"')
    safe_yaml_project = envelope["project_name"].replace('"', '\\"')
    safe_yaml_model = envelope["model_name"].replace('"', '\\"')

    lines: List[str] = [
        "---",
        f'session_id: "{envelope["session_id"]}"',
        f'title: "{safe_yaml_title}"',
        f'project: "{safe_yaml_project}"',
        f'model: "{safe_yaml_model}"',
        f'created_at: "{envelope["created_at"]}"',
        f'exported_at: "{envelope["exported_at"]}"',
        f'turns: {metrics["turn_count"]}',
        f'total_tokens: {metrics["total_tokens"]}',
        f'cost_usd: {metrics["session_cost_usd"]:.4f}',
        "---",
        "",
        f'# {envelope["title"]}',
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f'| **Session ID** | `{envelope["session_id"]}` |',
        f'| **Project** | `{envelope["project_name"]}` |',
        f'| **Model** | `{envelope["model_name"]}` |',
        f'| **Turns** | {metrics["turn_count"]} |',
        (
            f'| **Total Tokens** | {metrics["total_tokens"]:,} '
            f'({metrics["prompt_tokens"]:,} prompt / {metrics["completion_tokens"]:,} completion) |'
        ),
        f'| **Estimated Cost** | ${metrics["session_cost_usd"]:.4f} |',
        "",
    ]

    for turn in envelope["turns"]:
        lines.append("---")
        lines.append("")
        if turn["role"] == "user":
            lines.append("## User")
        else:
            m_label = turn.get("model_name") or envelope["model_name"]
            lines.append(f"## Assistant (`{m_label}`)")
        lines.append("")

        for att in turn.get("attachments", []):
            size_label = format_byte_size(att["approx_bytes"])
            lines.append(
                f'[Attached Image: {att["media_type"]}, ~{size_label}, sha256:{att["sha256_prefix"]}]'
            )
            lines.append("")

        for trace in turn.get("tool_traces", []):
            summary_label = html.escape(trace["display_label"])
            t_name = html.escape(trace["tool_name"])
            args_json = _escape_details_tag(
                json.dumps(trace["arguments"], indent=2, ensure_ascii=False)
            )
            res_text = _escape_details_tag(trace["result_content"])

            args_fence = _safe_code_fence(args_json, min_len=3)
            res_fence = _safe_code_fence(res_text, min_len=3)

            lines.append("<details>")
            lines.append(f"<summary>Tool Call: <code>{t_name}</code> ({summary_label})</summary>")
            lines.append("")
            lines.append("**Arguments:**")
            lines.append(f"{args_fence}json")
            lines.append(args_json)
            lines.append(args_fence)
            lines.append("")
            lines.append("**Output:**")
            lines.append(f"{res_fence}text")
            lines.append(res_text)
            lines.append(res_fence)
            lines.append("</details>")
            lines.append("")

        if turn["text_content"]:
            lines.append(turn["text_content"])
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_json_export(envelope: SessionExportEnvelope) -> str:
    """Renders the normalized SessionExportEnvelope into formatted JSON."""
    return json.dumps(envelope, indent=2, ensure_ascii=False) + "\n"


def render_html_export(envelope: SessionExportEnvelope) -> str:
    """Renders the normalized SessionExportEnvelope into a standalone HTML5 document."""
    metrics = envelope["metrics"]
    esc_title = html.escape(envelope["title"])
    esc_session_id = html.escape(envelope["session_id"])
    esc_project = html.escape(envelope["project_name"])
    esc_model = html.escape(envelope["model_name"])
    esc_exported = html.escape(envelope["exported_at"])

    turn_blocks: List[str] = []
    for turn in envelope["turns"]:
        is_user = turn["role"] == "user"
        role_class = "turn-user" if is_user else "turn-assistant"
        role_title = "User" if is_user else f"Assistant ({html.escape(turn.get('model_name') or envelope['model_name'])})"

        parts: List[str] = [
            f'<section class="turn {role_class}">',
            f'<header class="turn-header"><span class="role-badge">{role_title}</span></header>',
        ]

        for att in turn.get("attachments", []):
            size_label = format_byte_size(att["approx_bytes"])
            att_text = html.escape(
                f"[Attached Image: {att['media_type']}, ~{size_label}, sha256:{att['sha256_prefix']}]"
            )
            parts.append(f'<div class="attachment-badge">{att_text}</div>')

        for trace in turn.get("tool_traces", []):
            t_name = html.escape(trace["tool_name"])
            disp_label = html.escape(trace["display_label"])
            args_str = html.escape(json.dumps(trace["arguments"], indent=2, ensure_ascii=False))
            res_str = html.escape(trace["result_content"])
            status_cls = "tool-error" if trace["is_error"] else "tool-ok"

            parts.append(
                f'<details class="tool-trace {status_cls}">'
                f"<summary>Tool Call: <code>{t_name}</code> &mdash; {disp_label}</summary>"
                f'<div class="tool-body">'
                f'<div class="tool-section-label">Arguments</div>'
                f"<pre><code>{args_str}</code></pre>"
                f'<div class="tool-section-label">Output</div>'
                f"<pre><code>{res_str}</code></pre>"
                f"</div></details>"
            )

        if turn["text_content"]:
            esc_content = html.escape(turn["text_content"])
            parts.append(f'<div class="turn-content">{esc_content}</div>')

        parts.append("</section>")
        turn_blocks.append("\n".join(parts))

    turns_html = "\n".join(turn_blocks)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc_title} - Raven Session Export</title>
<style>
  :root {{
    --bg: #0f172a;
    --panel: #1e293b;
    --panel-alt: #162032;
    --text: #f8fafc;
    --muted: #94a3b8;
    --accent: #10b981;
    --user-accent: #3b82f6;
    --code-bg: #0b1120;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 32px 16px;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 1.6;
  }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  .doc-header {{
    background: var(--panel);
    padding: 24px;
    border-radius: 8px;
    margin-bottom: 24px;
  }}
  .doc-header h1 {{ margin: 0 0 16px 0; font-size: 1.5rem; color: var(--accent); }}
  .meta-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
    font-size: 0.875rem;
  }}
  .meta-item {{ background: var(--code-bg); padding: 10px 14px; border-radius: 6px; }}
  .meta-label {{ color: var(--muted); display: block; font-size: 0.75rem; text-transform: uppercase; }}
  .meta-val {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-weight: 600; }}
  .turn {{
    background: var(--panel);
    padding: 20px 24px;
    border-radius: 8px;
    margin-bottom: 16px;
  }}
  .turn-user {{ background: var(--panel-alt); }}
  .turn-header {{ margin-bottom: 12px; }}
  .role-badge {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    background: var(--accent);
    color: #052e16;
  }}
  .turn-user .role-badge {{ background: var(--user-accent); color: #eff6ff; }}
  .attachment-badge {{
    display: inline-block;
    background: var(--code-bg);
    color: var(--muted);
    padding: 6px 12px;
    border-radius: 4px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.82rem;
    margin-bottom: 12px;
  }}
  .turn-content {{
    white-space: pre-wrap;
    word-break: break-word;
    font-size: 0.95rem;
  }}
  details.tool-trace {{
    background: var(--code-bg);
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 12px;
  }}
  details.tool-trace summary {{
    cursor: pointer;
    font-size: 0.85rem;
    color: var(--muted);
    font-weight: 600;
  }}
  .tool-body {{ margin-top: 10px; }}
  .tool-section-label {{
    font-size: 0.75rem;
    text-transform: uppercase;
    color: var(--muted);
    margin: 8px 0 4px 0;
  }}
  pre {{
    background: #060a12;
    padding: 12px;
    border-radius: 4px;
    overflow-x: auto;
    margin: 0;
    font-size: 0.82rem;
  }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
</style>
</head>
<body>
  <div class="container">
    <header class="doc-header">
      <h1>{esc_title}</h1>
      <div class="meta-grid">
        <div class="meta-item"><span class="meta-label">Session ID</span><span class="meta-val">{esc_session_id}</span></div>
        <div class="meta-item"><span class="meta-label">Project</span><span class="meta-val">{esc_project}</span></div>
        <div class="meta-item"><span class="meta-label">Model</span><span class="meta-val">{esc_model}</span></div>
        <div class="meta-item"><span class="meta-label">Turns</span><span class="meta-val">{metrics["turn_count"]}</span></div>
        <div class="meta-item"><span class="meta-label">Total Tokens</span><span class="meta-val">{metrics["total_tokens"]:,}</span></div>
        <div class="meta-item"><span class="meta-label">Estimated Cost</span><span class="meta-val">${metrics["session_cost_usd"]:.4f}</span></div>
        <div class="meta-item"><span class="meta-label">Exported At</span><span class="meta-val">{esc_exported}</span></div>
      </div>
    </header>
    {turns_html}
  </div>
</body>
</html>
"""


def export_active_session(
    session_data: Dict[str, Any],
    raw_path_arg: str = "",
    workspace_dir: Optional[Path] = None,
    max_tool_output_chars: int = 10_000,
    app: Any = None,
) -> Dict[str, Any]:
    """
    Serializes and writes the active session transcript atomically to disk,
    and copies the resolved output path to the system clipboard.
    """
    try:
        envelope = build_export_envelope(
            session_data=session_data,
            max_tool_output_chars=max_tool_output_chars,
            truncate_tool_output=True,
        )

        if not envelope["turns"]:
            return {
                "success": False,
                "output_path": "",
                "format": "md",
                "bytes_written": 0,
                "turn_count": 0,
                "clipboard_copied": False,
                "error": "Cannot export an empty conversation.",
            }

        target_path, fmt = resolve_export_target(
            raw_path_arg=raw_path_arg,
            session_id=envelope["session_id"],
            title=envelope["title"],
            workspace_dir=workspace_dir,
        )

        if fmt == "json":
            rendered = render_json_export(envelope)
        elif fmt == "html":
            rendered = render_html_export(envelope)
        else:
            rendered = render_markdown_export(envelope)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_name(f".{target_path.name}.tmp")
        encoded_bytes = rendered.encode("utf-8")
        tmp_path.write_bytes(encoded_bytes)
        os.replace(tmp_path, target_path)

        clipboard_copied = False
        try:
            from agent.terminal_ui.chat_message import copy_to_system_clipboard
            clipboard_copied = bool(copy_to_system_clipboard(str(target_path), app=app))
        except Exception:
            clipboard_copied = False

        return {
            "success": True,
            "output_path": str(target_path),
            "format": fmt,
            "bytes_written": len(encoded_bytes),
            "turn_count": envelope["metrics"]["turn_count"],
            "clipboard_copied": clipboard_copied,
            "error": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "output_path": "",
            "format": "md",
            "bytes_written": 0,
            "turn_count": 0,
            "clipboard_copied": False,
            "error": f"Failed to export session transcript: {exc}",
        }
