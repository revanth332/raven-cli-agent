from pathlib import Path
import math
import os
import re
from collections import Counter
from agent.utils import get_project_root, get_active_project_name
from agent.core.compaction import should_compact_content, compact_content, save_compacted_memory
from datetime import datetime, timezone

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "in", "on",
    "for", "with", "by", "at", "from", "as", "that", "this", "it", "or",
    "and", "be", "have", "has", "had", "not", "but", "if", "into", "about",
    "how", "what", "when", "where", "why", "who", "which", "can", "could",
}

CANONICAL_PROJECT_SECTIONS = [
    "Tech Stack & Runtime",
    "Active Architecture & Key Modules",
    "Critical Constraints, Preferences",
    "Current/Ongoing Tasks",
]


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9_]+", (text or "").lower())
    return [t for t in tokens if len(t) >= 2 and t not in _STOPWORDS]


def chunk_debug_history(text: str) -> list[dict]:
    """
    Splits debug history into distinct logical chunks per error, parsing metadata if present.
    """
    chunks = []
    # Match entries starting with optional metadata HTML comment and ## Error:
    # Pattern: <!-- entry: id=(...) ts=(...) hits=(...) --> ## Error: ...
    sections = re.split(r"(?=(?:<!--\s*entry:[^>]*-->\s*)?## Error:)", text)
    for sec in sections:
        sec_content = sec.strip()
        if not sec_content or sec_content.startswith("# Debugging History"):
            continue
        if "## Error:" not in sec_content:
            continue

        meta_match = re.search(r"<!--\s*entry:\s*id=([^\s]+)\s+ts=([^\s]+)\s+hits=(\d+)\s*-->", sec_content)
        entry_id = meta_match.group(1) if meta_match else ""
        ts = meta_match.group(2) if meta_match else ""
        hits = int(meta_match.group(3)) if meta_match else 0

        chunks.append({
            "type": "debug_log",
            "content": sec_content,
            "id": entry_id,
            "ts": ts,
            "hits": hits,
        })
    return chunks


def chunk_markdown_file(file_path: Path, text: str) -> list[dict]:
    """
    Chunks standard markdown text by paragraph groupings under 1000 characters.
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    chunk_type = "concept_block" if "concepts" in str(file_path) else "global_memory_block"
    for p in paragraphs:
        p_strip = p.strip()
        if not p_strip:
            continue
        if len(current_chunk) + len(p_strip) < 1000:
            current_chunk += p_strip + "\n\n"
        else:
            if current_chunk.strip():
                chunks.append({
                    "type": chunk_type,
                    "content": current_chunk.strip()
                })
            current_chunk = p_strip + "\n\n"
    if current_chunk.strip():
        chunks.append({
            "type": chunk_type,
            "content": current_chunk.strip()
        })
    return chunks


def _collect_episodic_chunks() -> list[dict]:
    """
    Collects all episodic chunks from debug_history.md, concepts/*.md, and cross-project memory files.
    Global memory is strictly excluded since it is already injected directly into the system prompt.
    """
    debug_history_file = Path.home() / ".raven" / "debug_history.md"
    concepts_dir = Path.home() / ".raven" / "concepts"
    projects_dir = Path.home() / ".raven" / "memory" / "projects"
    current_project = get_active_project_name()

    collected = []

    if debug_history_file.exists():
        try:
            content = debug_history_file.read_text(encoding="utf-8")
            for ch in chunk_debug_history(content):
                ch["source"] = debug_history_file.name
                collected.append(ch)
        except Exception:
            pass

    if concepts_dir.exists():
        try:
            for f in sorted(concepts_dir.iterdir()):
                if f.is_file() and f.name.endswith(".md"):
                    content = f.read_text(encoding="utf-8")
                    for ch in chunk_markdown_file(f, content):
                        ch["source"] = f.name
                        collected.append(ch)
        except Exception:
            pass

    if projects_dir.exists():
        try:
            for f in sorted(projects_dir.iterdir()):
                # Exclude current active project from BM25 episodic chunks since active project memory is already in system prompt
                if f.is_file() and f.name.endswith(".md"):
                    proj_base_name = f.stem
                    if current_project and proj_base_name.lower() == current_project.lower():
                        continue
                    content = f.read_text(encoding="utf-8")
                    for ch in chunk_markdown_file(f, content):
                        ch["source"] = f"project:{proj_base_name}"
                        ch["type"] = "cross_project_memory"
                        collected.append(ch)
        except Exception:
            pass

    return collected


def _calculate_recency_and_utility_boost(chunk: dict) -> float:
    """
    Computes a multiplier for episodic chunk ranking based on:
    - Temporal decay: half-life of 90 days (lambda = ln(2) / 90 ~ 0.007702)
    - Utility boost: 1.0 + 0.15 * log(hits + 1)
    """
    ts_str = chunk.get("ts")
    hits = chunk.get("hits", 0)

    temporal_factor = 1.0
    if ts_str:
        try:
            # Parse ISO timestamp (support both Z and offset)
            ts_clean = ts_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_clean)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta_days = max(0.0, (now - dt).total_seconds() / 86400.0)
            decay_lambda = 0.693147 / 90.0  # ln(2) / 90 days half-life
            temporal_factor = math.exp(-decay_lambda * delta_days)
        except Exception:
            temporal_factor = 1.0

    utility_factor = 1.0 + (0.15 * math.log(max(0, hits) + 1.0))
    return temporal_factor * utility_factor


def _rank_episodic_chunks(query: str, chunks: list[dict], top_k: int = 3) -> list[dict]:
    """
    Ranks episodic memory chunks using Okapi BM25 + exact substring bonus + temporal decay & utility boost.
    Zero external dependencies; runs locally in <2ms across all LLM providers.
    """
    if not query or not query.strip() or not chunks:
        return []

    query_lower = query.strip().lower()
    query_tokens = _tokenize(query_lower)
    if not query_tokens:
        query_tokens = [w for w in re.findall(r"[a-z0-9_]+", query_lower) if w]
    if not query_tokens:
        return []

    doc_tokens_list = []
    doc_freqs = Counter()
    total_len = 0

    for ch in chunks:
        searchable_text = f"{ch.get('source', '')} {ch.get('content', '')}"
        tokens = _tokenize(searchable_text)
        doc_tokens_list.append(tokens)
        total_len += len(tokens)
        for unique_tok in set(tokens):
            doc_freqs[unique_tok] += 1

    num_docs = len(chunks)
    avgdl = (total_len / num_docs) if num_docs > 0 else 1.0
    k1 = 1.5
    b = 0.75

    scored = []
    for idx, ch in enumerate(chunks):
        tokens = doc_tokens_list[idx]
        doc_len = len(tokens)
        tf_counter = Counter(tokens)
        score = 0.0

        for q_tok in query_tokens:
            tf = tf_counter.get(q_tok, 0)
            if tf == 0:
                # Partial prefix/substring token match fallback
                for d_tok, count in tf_counter.items():
                    if len(q_tok) >= 4 and (q_tok in d_tok or d_tok in q_tok):
                        tf += count * 0.4
            if tf > 0:
                df = doc_freqs.get(q_tok, 0)
                idf = math.log(1.0 + (num_docs - df + 0.5) / (df + 0.5))
                denom = tf + k1 * (1.0 - b + b * (doc_len / max(avgdl, 1.0)))
                score += idf * ((tf * (k1 + 1.0)) / denom)

        content_lower = ch.get("content", "").lower()
        source_lower = ch.get("source", "").lower()
        if query_lower in content_lower or query_lower in source_lower:
            score += 3.0

        if score > 0:
            recency_utility = _calculate_recency_and_utility_boost(ch)
            final_score = score * recency_utility
            scored.append((final_score, idx, ch))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored[:top_k]]


def recall_memory(query: str) -> str:
    """
    Searches your global memory, debug history, and documented concepts for relevant past experiences, debug solutions, and technical insights.
    Args:
        query: Search query matching past experiences, errors, or concepts.
    """
    chunks = _collect_episodic_chunks()
    if not chunks:
        return "No relevant past memories, debug solutions, or concepts found."

    matches = _rank_episodic_chunks(query, chunks, top_k=3)
    if not matches:
        return "No relevant past memories, debug solutions, or concepts found."

    formatted_results = []
    for ch in matches:
        formatted_results.append(
            f"### Source: {ch['source']} (Type: {ch['type']})\n\n{ch['content']}"
        )

    return "\n\n---\n\n".join(formatted_results)


def get_memory_content():
    """
    Load Global memory content from the memory file if exists or creates a memory file.
    """
    memory_file = Path.home() / ".raven" / "memory" / "global_memory.md"

    if not memory_file.exists():
        memory_file.parent.mkdir(parents=True, exist_ok=True)
        default_memory = "You are Raven, my personal AI developer agent. Here is what you know about me:\n\n- I use Windows.\n- My main stack is React, Node, and Python."
        memory_file.write_text(default_memory, encoding="utf-8")
    return memory_file.read_text(encoding="utf-8")


def get_project_memory_info():
    """Loads or initializes memory specific to the active project folder."""
    project_name = get_active_project_name()
    if not project_name:
        return "", "No memory available yet."
    project_memory_file = Path.home() / ".raven" / "memory" / "projects" / (project_name + ".md")
    if not project_memory_file.exists():
        project_memory_file.parent.mkdir(parents=True, exist_ok=True)
        default_project_memory = (
            "## Tech Stack & Runtime\n\n"
            "## Active Architecture & Key Modules\n\n"
            "## Critical Constraints, Preferences\n\n"
            "## Current/Ongoing Tasks\n"
        )
        project_memory_file.write_text(default_project_memory, encoding="utf-8")
    return str(project_memory_file), project_memory_file.read_text(encoding="utf-8")


def get_active_projects():
    """
    Use this tool to get the paths of active projects.

    Returns:
    Full paths of the active projects memory files
    """
    projects = []
    projects_memory_folder = Path.home() / ".raven" / "memory" / "projects"
    if not projects_memory_folder.exists():
        return "No Projects available."
    for file in projects_memory_folder.iterdir():
        if file.is_file() and file.name.endswith(".md"):
            projects.append(str(file))
    if len(projects) <= 0:
        return "No Projects available."
    return projects


def _reconcile_global_memory_entry(existing_content: str, category: str, information: str) -> tuple[str, str]:
    """
    Reconciles a new global memory entry against existing bullets.
    Detects NOOP, REPLACE, or APPEND using normalized token similarity and negation/inversion keywords.
    Returns (action, updated_content).
    """
    cat_clean = (category or "fact").strip().lstrip("-").lower()
    info_clean = " ".join((information or "").strip().split())

    lines = existing_content.splitlines()
    new_tokens = set(_tokenize(info_clean))

    best_match_idx = -1
    best_similarity = 0.0

    for idx, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped.startswith("-"):
            continue
        # Extract existing text after "-category: " or "- "
        raw_text = re.sub(r"^-\s*([a-zA-Z_]+:\s*)?", "", line_stripped).strip()
        line_tokens = set(_tokenize(raw_text))
        if not line_tokens or not new_tokens:
            continue

        overlap = len(new_tokens & line_tokens)
        sim = overlap / max(len(new_tokens), len(line_tokens))
        if sim > best_similarity:
            best_similarity = sim
            best_match_idx = idx

    new_bullet = f"- {cat_clean}: {info_clean}"

    # If >85% token overlap, check if it's identical (NOOP) or an update/refinement
    if best_similarity >= 0.85 and best_match_idx >= 0:
        existing_line = lines[best_match_idx].strip()
        raw_existing = re.sub(r"^-\s*([a-zA-Z_]+:\s*)?", "", existing_line).strip().lower()
        if raw_existing == info_clean.lower():
            return "NOOP", existing_content
        # High overlap but not identical -> Replace old bullet in place
        lines[best_match_idx] = new_bullet
        return "REPLACE", "\n".join(lines) + "\n"

    # If 50%-85% overlap, check for contradiction keywords (e.g., 'not', 'never', 'always', 'do not')
    if best_similarity >= 0.50 and best_match_idx >= 0:
        existing_line = lines[best_match_idx].strip().lower()
        info_lower = info_clean.lower()
        contrast_words = {"not", "never", "always", "dislike", "prefer", "stop", "avoid", "only"}
        has_contrast = bool(contrast_words & (new_tokens ^ set(_tokenize(existing_line))))
        if has_contrast:
            # Replaces the contrasting rule
            lines[best_match_idx] = new_bullet
            return "REPLACE", "\n".join(lines) + "\n"

    # Distinct entry -> Append cleanly
    updated = existing_content.rstrip() + f"\n{new_bullet}\n"
    return "APPEND", updated


def save_to_memory(information: str, category: str):
    """
    Use this tool to save important facts, user preferences, project details, or newly learned concepts to long-term memory.
    Call this automatically when the user mentions something that would be useful for future interactions.
    Args:
        information: The exact text or factual insight to be memorized.
        category: The classification for this memory (e.g., 'preference', 'fact').
    """
    info_clean = " ".join((information or "").strip().split())
    cat_clean = (category or "fact").strip().lstrip("-")
    if not info_clean:
        return "Error: Memory information cannot be empty."

    existing_content = get_memory_content()
    action, updated_content = _reconcile_global_memory_entry(existing_content, cat_clean, info_clean)

    if action == "NOOP":
        return "Memory already contains this exact information."

    memory_file = Path.home() / ".raven" / "memory" / "global_memory.md"
    save_compacted_memory(str(memory_file), updated_content)
    if action == "REPLACE":
        return f"Reconciled and updated existing memory under category '{cat_clean}'."
    return "New data added to memory successfully"


def _normalize_section_name(section: str) -> str:
    s = (section or "").strip().lower()
    if "tech" in s or "stack" in s or "runtime" in s:
        return "Tech Stack & Runtime"
    if "arch" in s or "module" in s:
        return "Active Architecture & Key Modules"
    if "constraint" in s or "prefer" in s:
        return "Critical Constraints, Preferences"
    if "task" in s or "current" in s or "ongoing" in s:
        return "Current/Ongoing Tasks"
    return "Current/Ongoing Tasks"


def _parse_project_memory_sections(raw_markdown: str) -> dict[str, str]:
    sections = {sec: "" for sec in CANONICAL_PROJECT_SECTIONS}
    current_sec = None
    buffer = []

    for line in (raw_markdown or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            continue
        if stripped.startswith("## "):
            if current_sec is not None:
                sections[current_sec] = "\n".join(buffer).strip()
            header_title = stripped[3:].strip()
            current_sec = _normalize_section_name(header_title)
            buffer = [sections[current_sec]] if sections.get(current_sec) else []
        else:
            if current_sec is not None:
                buffer.append(line)

    if current_sec is not None:
        sections[current_sec] = "\n".join(buffer).strip()

    return sections


def _render_project_memory_sections(sections: dict[str, str]) -> str:
    blocks = []
    for sec in CANONICAL_PROJECT_SECTIONS:
        body = (sections.get(sec) or "").strip()
        if body:
            blocks.append(f"## {sec}\n\n{body}")
        else:
            blocks.append(f"## {sec}")
    return "\n\n".join(blocks) + "\n"


def update_project_memory(section: str, content: str, mode: str = "replace") -> str:
    """
    Updates a specific section of the active project's memory file atomically.
    Args:
        section: Target section ('Tech Stack & Runtime', 'Active Architecture & Key Modules', 'Critical Constraints, Preferences', or 'Current/Ongoing Tasks').
        content: Markdown bullet points to write into the section.
        mode: 'replace' to overwrite the section body, or 'append' to add new bullet points to the section.
    """
    project_memory_path, raw_memory = get_project_memory_info()
    if not project_memory_path:
        return "Error: No active project directory found."

    target_section = _normalize_section_name(section)
    sections = _parse_project_memory_sections(raw_memory)
    clean_new = (content or "").strip()

    if mode and mode.strip().lower() == "append" and sections.get(target_section):
        existing_body = sections[target_section].strip()
        if clean_new and clean_new.lower() not in existing_body.lower():
            sections[target_section] = f"{existing_body}\n{clean_new}"
    else:
        sections[target_section] = clean_new

    rendered = _render_project_memory_sections(sections)

    if should_compact_content(rendered):
        global_mem = get_memory_content()
        compaction_res = compact_content(rendered, global_memory=global_mem)
        if compaction_res.get("success") and compaction_res.get("content"):
            rendered = compaction_res["content"]

    save_compacted_memory(project_memory_path, rendered)
    return f"Successfully updated project memory section '{target_section}'."


def log_successful_debug(error_description: str, solution: str) -> str:
    """
    Logs a successfully resolved error and its detailed solution to global debug history for future reference.
    Args:
        error_description: The error message or description of the issue.
        solution: The exact fix or steps taken to resolve the error.
    """
    debug_file = Path.home() / ".raven" / "debug_history.md"

    if not debug_file.exists():
        debug_file.parent.mkdir(parents=True, exist_ok=True)
        debug_file.write_text("# Debugging History & Error Resolutions\n\n", encoding="utf-8")

    project_name = get_active_project_name()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry_id = f"dbg_{int(datetime.now(timezone.utc).timestamp())}"
    meta_header = f"<!-- entry: id={entry_id} ts={now_iso} hits=1 -->"

    log_entry = f"\n{meta_header}\n## Error: {error_description}\n"
    if project_name:
        log_entry += f"- **Project**: {project_name}\n"
    log_entry += f"- **Solution**: {solution}\n"

    with open(debug_file, "a", encoding="utf-8") as f:
        f.write(log_entry)
    return "Debug session successfully logged in global history."


def save_concept(concept_name: str, explanation: str) -> str:
    """
    Saves a detailed markdown explanation of a concept, design pattern, or architecture that the user is deeply exploring or has high interest in.
    Args:
        concept_name: The name of the concept or technology (e.g. 'React Context API', 'Docker Setup').
        explanation: A precise, organized explanation of the concept in markdown format.
    """
    safe_name = concept_name.lower().replace(" ", "_")
    concept_file = Path.home() / ".raven" / "concepts" / f"{safe_name}.md"

    concept_file.parent.mkdir(parents=True, exist_ok=True)
    concept_file.write_text(f"# Concept: {concept_name}\n\n{explanation}\n", encoding="utf-8")
    return f"Concept '{concept_name}' successfully documented."


def update_architecture_map(mermaid_code: str, explanation: str):
    """
    Creates or updates the architecture.md file with a Mermaid.js diagram of the project.
    Args:
        mermaid_code: The raw Mermaid.js graph code (e.g., 'graph TD\n A-->B'). Do not include markdown backticks.
        explanation: A brief text explanation of the architecture.
    """
    try:
        active_dir = get_project_root()
        if not active_dir:
            return "No active project directory found."
        archtecture_file = active_dir / "architecture.md"
        content = f"Project architecture:\n\n {explanation} \n\n ```mermaid\n{mermaid_code}\n```\n"
        archtecture_file.write_text(content, "utf-8")
        return f"Successfully generated architecture map at {archtecture_file.name}."
    except Exception as e:
        return f"Failed to update architecture map: {e}"
