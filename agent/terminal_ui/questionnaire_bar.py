from typing import Optional, Dict, Any, List, Callable, Tuple
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button
from textual.widget import Widget
from textual import events


def parse_option_display(opt: str) -> Tuple[str, str, str]:
    """Parses an option string into (short_name, main_title, subtext)
    for structured visual card presentation.
    """
    text = str(opt).strip()
    short_name = ""
    main_title = text
    subtext = ""

    if " - " in text:
        parts = text.split(" - ", 1)
        main_title = parts[0].strip()
        subtext = parts[1].strip()
    elif ": " in text:
        parts = text.split(": ", 1)
        main_title = parts[0].strip()
        subtext = parts[1].strip()
    elif " (" in text and text.endswith(")"):
        idx = text.find(" (")
        main_title = text[:idx].strip()
        subtext = text[idx + 2 : -1].strip()

    words = main_title.split()
    if len(words) <= 2:
        short_name = main_title
    else:
        short_name = words[0]

    return short_name, main_title, subtext


def find_recommended_index(options: List[str], recommended: str) -> int:
    """Finds the index of the recommended option using exact, prefix, or fuzzy matching."""
    if not options or not recommended:
        return 0

    rec_clean = str(recommended).strip().lower()

    # 1. Exact match (case-insensitive)
    for idx, opt in enumerate(options):
        if opt.strip().lower() == rec_clean:
            return idx

    # 2. Check if recommended is an explicit option number e.g. "1", "option 1", "[1]"
    digits = "".join(ch for ch in rec_clean if ch.isdigit())
    if digits:
        try:
            val = int(digits) - 1
            if 0 <= val < len(options) and (
                rec_clean.startswith("option")
                or rec_clean == digits
                or rec_clean.startswith(f"[{digits}]")
            ):
                return val
        except Exception:
            pass

    # 3. Main title / short name matching
    _, rec_title, _ = parse_option_display(recommended)
    for idx, opt in enumerate(options):
        _, opt_title, _ = parse_option_display(opt)
        if rec_title and (
            rec_title.lower() == opt_title.lower()
            or opt_title.lower().startswith(rec_title.lower())
        ):
            return idx

    # 4. Prefix or substring matching
    for idx, opt in enumerate(options):
        opt_lower = opt.strip().lower()
        if opt_lower.startswith(rec_clean) or rec_clean.startswith(opt_lower):
            return idx
        if rec_clean in opt_lower or opt_lower in rec_clean:
            return idx

    return 0


class OptionCardWidget(Vertical):
    """Horizontal card widget representing a single selectable decision option."""

    def __init__(
        self,
        index: int,
        full_text: str,
        is_recommended: bool = False,
        is_selected: bool = False,
        on_select: Optional[Callable[[int], None]] = None,
    ) -> None:
        classes = "option-card" + (" selected" if is_selected else "")
        super().__init__(classes=classes)
        self.option_index = index
        self.full_text = full_text
        self.is_recommended = is_recommended
        self.is_selected = is_selected
        self.on_select = on_select

    def compose(self) -> ComposeResult:
        _, main_title, subtext = parse_option_display(self.full_text)
        top_markup = f"[bold #10B981][{self.option_index + 1}][/bold #10B981]"
        if self.is_recommended:
            top_markup += "  [bold #10B981][RECOMMENDED][/bold #10B981]"

        yield Static(top_markup, classes="card-top-badge")
        yield Static(f"[bold]{main_title}[/bold]", classes="card-title")
        if subtext:
            yield Static(f"[dim #94A3B8]{subtext}[/dim #94A3B8]", classes="card-subtext")

    def on_click(self, event: events.Click) -> None:
        if self.on_select:
            self.on_select(self.option_index)
        event.stop()


class QuestionnaireBar(Widget):
    """In-stream action container mounted immediately above the bottom input bar
    for structured decision-making without floating modals.
    Takes custom decision or confirmation directly from the existing chat input box.
    """

    def __init__(
        self,
        title: str,
        questions: List[Dict[str, Any]],
        on_complete: Callable[[Dict[str, Any]], None],
        on_step_change: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(id="questionnaire_bar")
        self.batch_title = title or "Architectural Decisions"
        self.questions = questions or []
        self.on_complete = on_complete
        self.on_step_change = on_step_change
        self.current_index = 0
        self.selected_option_index = 0
        self.answers: Dict[str, str] = {}

    def compose(self) -> ComposeResult:
        with Horizontal(id="qbar_header"):
            yield Static("", id="qbar_header_left")
            yield Static(
                "[dim #64748B][1-4] Select  │  [Enter] Accept  │  [Esc] Cancel[/dim #64748B]",
                id="qbar_header_right",
            )

        with Vertical(id="qbar_question_box"):
            yield Static("", id="qbar_question_text")
            yield Static("", id="qbar_question_context")

        yield Horizontal(id="qbar_cards_row")

        with Horizontal(id="qbar_footer_row"):
            yield Static("", id="qbar_footer_hint")
            with Horizontal(id="qbar_footer_buttons"):
                yield Button("Cancel [Esc]", id="qbar_btn_cancel")
                yield Button("Accept [Enter]", id="qbar_btn_accept", variant="primary")

    def on_mount(self) -> None:
        self.load_active_question()

    def get_current_question(self) -> Optional[Dict[str, Any]]:
        if 0 <= self.current_index < len(self.questions):
            return self.questions[self.current_index]
        return None

    def get_selected_label(self) -> str:
        q = self.get_current_question()
        if not q:
            return ""
        options = q.get("options", [])
        if 0 <= self.selected_option_index < len(options):
            opt = options[self.selected_option_index]
            _, main_title, _ = parse_option_display(opt)
            return main_title
        return ""

    def load_active_question(self) -> None:
        if not self.questions or self.current_index >= len(self.questions):
            self.finish_questionnaire(cancelled=False)
            return

        q = self.questions[self.current_index]
        options = q.get("options", [])
        recommended = q.get("recommended", "")

        # Resilient matching for recommended option index
        rec_index = find_recommended_index(options, recommended)
        self.selected_option_index = rec_index

        # Update Header
        hdr_left = self.query_one("#qbar_header_left", Static)
        hdr_left.update(
            f"[bold #10B981]▌[/bold #10B981] [bold #F8FAFC]{self.batch_title}[/bold #F8FAFC]  "
            f"[bold #10B981][{self.current_index + 1}/{len(self.questions)}][/bold #10B981]"
        )

        # Update Question Text & Context
        q_text = self.query_one("#qbar_question_text", Static)
        q_text.update(q.get("question", "Decision required:"))

        q_ctx = self.query_one("#qbar_question_context", Static)
        ctx = q.get("context", "")
        q_ctx.update(f"[dim #94A3B8]{ctx}[/dim #94A3B8]" if ctx else "")

        # Re-mount Cards Row
        cards_row = self.query_one("#qbar_cards_row", Horizontal)
        cards_row.remove_children()

        new_cards = []
        for idx, opt in enumerate(options):
            card = OptionCardWidget(
                index=idx,
                full_text=opt,
                is_recommended=(idx == rec_index),
                is_selected=(idx == self.selected_option_index),
                on_select=self.select_option,
            )
            new_cards.append(card)

        if new_cards:
            cards_row.mount(*new_cards)

        # Update Footer
        footer_hint = self.query_one("#qbar_footer_hint", Static)
        count_opts = len(options)
        opts_hint = f"1-{count_opts}" if count_opts > 1 else "1"
        footer_hint.update(
            f"[dim #64748B]Step {self.current_index + 1} of {len(self.questions)} "
            f"(Click card, type {opts_hint}, or type custom response below)[/dim #64748B]"
        )

        btn_accept = self.query_one("#qbar_btn_accept", Button)
        if self.current_index == len(self.questions) - 1:
            btn_accept.label = "Complete [Enter]"
        else:
            btn_accept.label = "Accept [Enter]"

        if self.on_step_change:
            self.on_step_change()

    def select_option(self, idx: int) -> None:
        q = self.get_current_question()
        if not q:
            return
        options = q.get("options", [])
        if 0 <= idx < len(options):
            self.selected_option_index = idx
            for i, card in enumerate(self.query(OptionCardWidget)):
                if i == idx:
                    card.add_class("selected")
                else:
                    card.remove_class("selected")
            if self.on_step_change:
                self.on_step_change()

    def select_previous(self) -> None:
        if self.selected_option_index > 0:
            self.select_option(self.selected_option_index - 1)

    def select_next(self) -> None:
        q = self.get_current_question()
        if q and self.selected_option_index < len(q.get("options", [])) - 1:
            self.select_option(self.selected_option_index + 1)

    def submit_answer(self, user_text: str = "") -> bool:
        """Processes answer submitted from the chat input box or Accept button.
        Returns True if more questions remain, False if questionnaire is finished.
        """
        if self.current_index >= len(self.questions):
            self.finish_questionnaire(cancelled=False)
            return False

        q = self.questions[self.current_index]
        qid = q.get("id", f"decision_{self.current_index + 1}")
        options = q.get("options", [])

        text = (user_text or "").strip()
        if text:
            # If user typed a single number corresponding to an option
            if text.isdigit():
                idx = int(text) - 1
                if 0 <= idx < len(options):
                    chosen_answer = options[idx]
                else:
                    chosen_answer = text
            else:
                chosen_answer = text
        else:
            if 0 <= self.selected_option_index < len(options):
                chosen_answer = options[self.selected_option_index]
            else:
                chosen_answer = q.get("recommended", options[0] if options else "")

        self.answers[qid] = chosen_answer

        # Advance or finish
        self.current_index += 1
        if self.current_index < len(self.questions):
            self.load_active_question()
            return True
        else:
            self.finish_questionnaire(cancelled=False)
            return False

    def finish_questionnaire(self, cancelled: bool = False) -> None:
        if cancelled:
            self.on_complete({"status": "cancelled", "answers": {}})
        else:
            self.on_complete({"status": "completed", "answers": self.answers})

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "qbar_btn_accept":
            self.submit_answer("")
        elif event.button.id == "qbar_btn_cancel":
            self.finish_questionnaire(cancelled=True)

