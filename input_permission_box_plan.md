# Implementation Plan - Input Box Permission Prompt & Instruction Feedback

Replace the inline history `PermissionBox` with a unified input-bar permission prompt that accepts direct keyboard shortcuts (`Enter` to approve, typed feedback + `Enter` to give feedback, or `Esc`/`No` to deny).

## 1. Objectives & Behavior
- **Location**: Rendered directly in `#bottom_bar` (replacing or wrapping `ChatInput` & status area during permission requests).
- **Default Action (`Enter` with empty input or "Yes, Allow" button)**: Grants tool execution permission.
- **Feedback Action (Typed text + `Enter`)**: Denies tool execution and passes the feedback instruction back to Raven as a tool error message (e.g., `User denied permission and provided instructions: '<instruction>'`).
- **Deny Action ("No, Deny" button or `Esc`)**: Denies tool execution (`User denied permission.`).
- **Post-Action**: Bottom bar seamlessly switches back to standard `ChatInput` state.

## 2. Architectural Changes
1. **`agent/terminal_ui/permission_box.py`**:
   - Refactor `PermissionBox` / `PermissionBar` widget into a widget suited for placement inside `#bottom_bar`.
   - Include action header, tool parameters preview, and "Yes, Allow (Enter)" / "No, Deny" controls.
2. **`agent/terminal_ui/app.py`**:
   - Add state management for active permission requests.
   - Update `ask_permission_ui()` to show the bottom permission bar, adjust `ChatInput` placeholder/prompt, and focus input.
   - Update `on_chat_input_submitted()` and key handling so submitting empty input resolves permission = `True`, while non-empty input resolves permission = `False` with the instruction string.
   - Update `stream_response()` in `app.py` to process `permission_result` and `permission_instruction`.
3. **`agent/terminal_ui/chat_input.py`** & CSS:
   - Add styling rules for permission mode in CSS (`#bottom_bar`, permission notice banner, buttons).

## 3. Step-by-Step Implementation Steps
1. Create `input_permission_box_plan.md` (This file).
2. Refactor `permission_box.py` into a modern `#bottom_bar` permission banner (`PermissionBar`).
3. Update `app.py` UI layout, CSS styles, `ask_permission_ui`, and input handlers.
4. Update tool permission execution handling in `stream_response` thread.
5. Run unit tests and verify functionality.
