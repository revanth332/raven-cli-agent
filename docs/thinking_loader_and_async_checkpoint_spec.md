# Thinking Loader Latency Elimination and Async Checkpointing Specification

## 1. Overview & Problem Statement

### 1.1 Problem
Submitting a prompt in the Terminal UI currently experiences a 10 to 30 second perceived freeze before the `"Thinking..."` animated loader appears.

### 1.2 Root Causes
1. **Deferred UI Mounting**: The `ThinkingMessage` widget is mounted inside `stream_response` worker thread *after* pre-flight operations instead of immediately upon user submission on the main thread.
2. **Synchronous Pre-turn Checkpointing**: `create_checkpoint("latest-checkpoint")` runs synchronously on the request initiation path. It executes multiple Windows `git.exe` subprocesses (`rev-parse`, `diff`, `status --porcelain`) and disk I/O operations (`shutil.copy2` for untracked workspace files), blocking turn startup for several seconds.
3. **Synchronous Auto-Compaction Blind Spot**: When token count exceeds the compaction threshold (60k tokens), `compact_history()` triggers a synchronous non-streaming LLM summarization call without notifying the UI, resulting in apparent freezing.

---

## 2. Architecture & Execution Flow

### 2.1 Before vs. After Flow

```text
[BEFORE - 10-30s Latency]
User Submit
  │
  ├──> Mount User Message
  └──> Spawn Worker (stream_response)
         │
         ├──> create_checkpoint() [BLOCKING: Subprocesses + Disk I/O (3-15s)]
         ├──> LoopGuard init
         ├──> Mount 'Thinking...' (Finally mounted after 10-30s)
         └──> LLM Stream Request

[AFTER - 0ms Instant Feedback]
User Submit
  │
  ├──> Mount User Message (0ms)
  ├──> Mount ThinkingMessage (0ms - Instant Visual Feedback)
  └──> Spawn Worker (stream_response)
         │
         ├──> Spawn Background Thread: create_checkpoint() (NON-BLOCKING)
         ├──> Pre-flight Checks / LoopGuard
         ├──> [Optional: If compacting -> Update loader to "Compacting history..."]
         └──> LLM Stream Request (Immediate connection)
```

---

## 3. Detailed Component Specifications

### 3.1 Immediate UI Mount on Submission (`agent/terminal_ui/app.py`)
* In `on_chat_input_submitted(self, event)`:
  1. Mount `ChatMessageWidget` (user turn) to `#history`.
  2. Clear the input widget and scroll to end.
  3. Immediately instantiate and mount `ThinkingMessage` into `#thinking_container` on the main UI thread.
  4. Pass the mounted loader reference (or clean container handle) to `stream_response` worker.
* Ensure slash commands (e.g., `/explain`, `/coach`, `/review`) and multimodal image submissions also immediately mount the loader before delegating execution to background workers.

### 3.2 Asynchronous Non-Blocking Checkpointing
* Move `create_checkpoint("latest-checkpoint")` out of the critical path of `stream_response`.
* Run checkpoint creation inside a dedicated fire-and-forget background daemon thread:
  ```python
  import threading

  def _async_auto_checkpoint():
      try:
          create_checkpoint("latest-checkpoint")
      except Exception:
          pass

  threading.Thread(target=_async_auto_checkpoint, daemon=True, name="AutoCheckpointWorker").start()
  ```
* **Thread Safety**: Ensure `_async_auto_checkpoint` does not block message dispatching, LLM stream consumption, or UI updates.
* **Error Isolation**: All exceptions during async checkpointing must be caught and ignored or logged silently without interrupting the user turn.

### 3.3 Auto-Compaction Real-Time Status Feedback
* When `send_message_stream()` detects that token count exceeds the threshold and triggers `compact_history()`:
  - If a status callback or UI hook is available, update the loader text to `● Compacting conversation history...`.
  - Once compaction completes, revert the loader text to `● Thinking...`.

### 3.4 Thinking Loader Lifecycle Management
* **Single Instance per Active Container**: Prevent duplicate loaders by clearing any lingering widgets in `#thinking_container` before mounting a new `ThinkingMessage`.
* **Tool Call Transition**: When an AI response yields tool calls or text tokens, the `ThinkingMessage` is unmounted cleanly and replaced by the chronological `ChatMessageWidget` (Raven card) or tool execution indicators.
* **Retry Rounds**: If the agent enters multiple tool calling loops, re-mount or reset the `ThinkingMessage` inside `#thinking_container` at the beginning of each tool loop round.

---

## 4. Verification & Acceptance Criteria

1. **Instant Feedback (<50ms)**: Pressing `Enter` in the chat input must immediately render the animated `● Thinking...` loader without perceptible lag.
2. **Zero Checkpoint Stall**: Checkpointing operations must run in the background without adding latency to the first token time or response streaming.
3. **No Duplicate Loaders**: Only one thinking animation should ever be visible at any given moment.
4. **Clean Unmounting**: The thinking loader must automatically unmount when streaming starts or tool calls execute.
5. **No Regressions**: Reverting/restoring checkpoints via `/checkpoint` or checkpoint tools continues to function reliably.
