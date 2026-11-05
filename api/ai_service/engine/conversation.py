"""Guided multi-turn conversation.

The server keeps nothing between turns. The browser sends back the state it
was given, and every turn re-assesses the child's words from scratch and
merges the result, so severity can only go up. Any free text, at any step,
is checked for danger first. Nothing here writes a message to a child other
than reviewed templates and approved knowledge entries.
"""
import logging
import re

from .chat import SHORT_MESSAGE_LIMIT, build_chat_response, helpline_line
from .config import Settings
from .content import select_bundle
from .retrieval import load_knowledge_base, search
from .routing import build_routing
from .schemas import (
    BotMessage,
    CaseDraft,
    Category,
    Choice,
    ConversationState,
    MAX_NARRATIVE_ENTRIES,
    MAX_STATE_RULES,
    MessageRequest,
    Severity,
    TriageResult,
    TurnRequest,
    TurnResponse,
)
from .triage import safe_triage

logger = logging.getLogger("habari.ai")

MAX_CLARIFY = 2
EVIDENCE_ENTRY_ID = "keep-evidence"
_SHORT_CHANNELS = frozenset({"sms", "ussd"})
_WHO_RELEVANT = frozenset({Category.ABUSE, Category.SEXTORTION, Category.GROOMING, Category.HARASSMENT})
_TRUSTED_ROLES = frozenset({"family", "teacher", "guardian"})

_RATING_FLOOR = {"feel_lot": Severity.S2, "feel_scared": Severity.S3, "feel_danger": Severity.S4}
_RATING_RANK = {"feel_little": 1, "feel_lot": 2, "feel_scared": 3, "feel_danger": 4}

_STEP_CHOICES = {
    "ask_feeling": ("feel_little", "feel_lot", "feel_scared", "feel_danger", "feel_skip"),
    "ask_now": ("yes", "no", "not_sure"),
    "ask_who": ("stranger", "online_contact", "peer", "family", "teacher", "guardian", "unknown"),
    "offer": ("talk_to_person", "report_privately", "keep_proof", "just_information", "done"),
    "report_review": ("confirm_send", "edit", "not_now"),
    "danger_check": ("safe_yes", "safe_no"),
}


def _pack(text: str, limit: int) -> list[str]:
    """Split text at sentence, then word, boundaries so each part fits one SMS."""
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        while len(sentence) > limit:
            cut = sentence.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            if current:
                parts.append(current)
                current = ""
            parts.append(sentence[:cut])
            sentence = sentence[cut:].lstrip()
        if not sentence:
            continue
        candidate = f"{current} {sentence}" if current else sentence
        if len(candidate) <= limit:
            current = candidate
        else:
            parts.append(current)
            current = sentence
    if current:
        parts.append(current)
    return parts


def _result_from_state(state: ConversationState) -> TriageResult:
    return TriageResult(
        severity=state.severity,
        category=state.category,
        confidence=state.confidence,
        matched_rules=state.rules,
        danger=state.danger,
        human_review=state.human_review or state.severity.rank >= Severity.S3.rank,
        external_only=state.external_only,
        needs_clarification=False,
    )


def _merge(state: ConversationState, result: TriageResult) -> ConversationState:
    """Fold a new assessment into the state. Severity and flags only ever go up."""
    higher = result.severity.rank > state.severity.rank
    same = result.severity.rank == state.severity.rank
    take_category = higher or (same and result.category != Category.OTHER) or state.category == Category.OTHER
    return state.model_copy(
        update={
            "severity": Severity.from_rank(max(state.severity.rank, result.severity.rank)),
            "category": result.category if take_category else state.category,
            "confidence": result.confidence,
            "rules": list(dict.fromkeys(state.rules + result.matched_rules))[:MAX_STATE_RULES],
            "external_only": state.external_only or result.external_only,
            "human_review": state.human_review or result.human_review,
            "danger": state.danger or result.danger,
        }
    )


def _apply_rating(state: ConversationState) -> ConversationState:
    """The child's own rating is a floor. It can raise severity and never lowers it."""
    floor = _RATING_FLOOR.get(state.self_rating)
    if floor is None or state.severity.rank >= floor.rank:
        return state
    return state.model_copy(
        update={
            "severity": floor,
            "danger": state.danger or floor == Severity.S4,
            "human_review": state.human_review or floor.rank >= Severity.S3.rank,
        }
    )


class _Context:
    def __init__(self, request: TurnRequest, settings: Settings):
        self.request = request
        self.settings = settings
        self.bundle, self.language_used, self.fell_back = select_bundle(request.language)
        self.flow = self.bundle["flow"]
        self.short = request.channel in _SHORT_CHANNELS
        self._option_labels = {o["id"]: o["label"] for o in self.bundle["path_options"]}

    # text helpers ----------------------------------------------------------
    def prompt(self, key: str, **values: str) -> str:
        text = self.flow["prompts"][key]["short" if self.short else "long"]
        for name, value in values.items():
            text = text.replace("{" + name + "}", value)
        return text

    def say(self, key: str, **values: str) -> BotMessage:
        return BotMessage(kind="text", text=self.prompt(key, **values))

    def category_label(self, category: Category) -> str:
        return self.flow["category_labels"][category.value]["short" if self.short else "label"]

    def label(self, choice_id: str) -> str:
        entry = self.flow["choices"][choice_id]
        if self.short:
            return entry["short"]
        return entry.get("label") or self._option_labels[choice_id]

    def helpline_message(self) -> BotMessage:
        return BotMessage(kind="text", text=helpline_line(self.bundle, self.settings.helpline_number, self.short))

    # response building ------------------------------------------------------
    def choices_for(self, state: ConversationState) -> list[Choice]:
        return [Choice(id=i, label=self.label(i)) for i in _STEP_CHOICES.get(state.step, ())]

    def respond(
        self,
        state: ConversationState,
        messages: list[BotMessage],
        case_draft: CaseDraft | None = None,
    ) -> TurnResponse:
        choices = self.choices_for(state)
        if self.short:
            messages = [
                BotMessage(kind=m.kind, text=part)
                for m in messages
                for part in _pack(m.text, SHORT_MESSAGE_LIMIT)
            ]
        menu = None
        if self.short and choices:
            menu = " ".join(f"{n}. {c.label}" for n, c in enumerate(choices, start=1))
        assessment = _result_from_state(state)
        return TurnResponse(
            state=state,
            messages=messages,
            choices=choices,
            menu_text=menu,
            accepts_text=state.step != "done",
            ended=state.step == "done",
            assessment=assessment,
            routing=build_routing(assessment),
            case_draft=case_draft,
            language_used=self.language_used,
            needs_native_review=self.fell_back,
            content_review_status=self.bundle["meta"]["review_status"],
            helpline=self.settings.helpline_number,
            helpline_configured=self.settings.helpline_number is not None,
        )

    # assessment ---------------------------------------------------------------
    def assess(self, state: ConversationState, text: str | None, hint: str | None = None):
        """Re-assess everything the child has said so far. Returns (state, whole_result, fresh_danger)."""
        narrative = list(state.narrative)
        if text:
            narrative.append(text)
            narrative = narrative[-MAX_NARRATIVE_ENTRIES:]
        state = state.model_copy(update={"narrative": narrative})
        fresh_danger = bool(text) and safe_triage(text, language=self.request.language).danger
        result = safe_triage(
            " ".join(narrative) if narrative else "hello",
            language=self.request.language,
            happening_now=state.happening_now,
            alleged_role=state.alleged_role,
            category_hint=hint,
        )
        merged = _apply_rating(_merge(state, result))
        if fresh_danger:
            merged = merged.model_copy(update={"danger": True})
        return merged, result, fresh_danger

    def reply_messages(self, state: ConversationState) -> list[BotMessage]:
        """The reviewed reply for what the child described, plus guidance and safe actions when appropriate."""
        last_text = state.narrative[-1]
        request = MessageRequest(
            message=last_text, language=self.request.language, channel=self.request.channel
        )
        guidance = self._guidance(state, last_text)
        response = build_chat_response(request, _result_from_state(state), self.settings)
        messages = [BotMessage(kind="danger" if state.danger else "text", text=response.reply)]
        if guidance is not None:
            messages.append(BotMessage(kind="guidance", title=guidance.entry.title, text=guidance.entry.answer))
        if not state.danger and not self.short:
            messages.append(
                BotMessage(
                    kind="list",
                    title=self.prompt("safe_actions_title"),
                    items=[action.text for action in response.safe_actions],
                )
            )
        return messages

    def _guidance(self, state: ConversationState, text: str):
        if self.short or self.language_used != "en" or state.danger or state.severity.rank > Severity.S2.rank:
            return None
        try:
            return search(text, "en", self.settings).match
        except Exception as exc:  # noqa: BLE001 - guidance is optional
            logger.error("guidance lookup failed with %s", type(exc).__name__)
            return None

    # flow control ---------------------------------------------------------------
    def danger_turn(self, state: ConversationState) -> TurnResponse:
        state = state.model_copy(update={"step": "danger_check"})
        messages = self.reply_messages(state)
        messages.append(self.say("danger_check"))
        return self.respond(state, messages)

    def next_question(self, state: ConversationState, messages: list[BotMessage]) -> TurnResponse:
        """Ask only what is still missing, then offer the child their options."""
        if not state.asked_feeling and not state.danger:
            return self.respond(state.model_copy(update={"step": "ask_feeling"}), messages + [self.say("ask_feeling")])
        if state.severity.rank >= Severity.S2.rank:
            if state.happening_now is None and not state.asked_now:
                return self.respond(state.model_copy(update={"step": "ask_now"}), messages + [self.say("ask_now")])
            if (
                state.alleged_role is None
                and not state.asked_who
                and not state.external_only
                and state.category in _WHO_RELEVANT
            ):
                return self.respond(state.model_copy(update={"step": "ask_who"}), messages + [self.say("ask_who")])
        return self.respond(state.model_copy(update={"step": "offer"}), messages + [self.say("offer")])

    def offer_turn(self, state: ConversationState, messages: list[BotMessage]) -> TurnResponse:
        return self.respond(state.model_copy(update={"step": "offer"}), messages + [self.say("offer")])

    def report_review(self, state: ConversationState, messages: list[BotMessage]) -> TurnResponse:
        state = state.model_copy(update={"step": "report_review"})
        who = [self.say("report_who_external" if state.external_only else "report_who_default")]
        if state.severity.rank >= Severity.S3.rank and not state.external_only:
            who.append(self.say("report_who_serious"))
        what = self.prompt("report_what", category=self.category_label(state.category))
        if self.short:
            review = [BotMessage(kind="text", text=what)] + who
        else:
            words = self.prompt("report_words", narrative=" ".join(state.narrative))
            review = [
                BotMessage(
                    kind="list",
                    title=self.prompt("report_title"),
                    items=[what, words] + [m.text for m in who],
                )
            ]
        return self.respond(state, messages + [self.say("report_intro")] + review + [self.say("report_confirm")])


# Handlers ------------------------------------------------------------------------

def _after_description(ctx: _Context, state: ConversationState) -> TurnResponse:
    messages = ctx.reply_messages(state)
    return ctx.next_question(state, messages)


def _handle_describe(ctx: _Context, state: ConversationState, text: str) -> TurnResponse:
    state, result, fresh_danger = ctx.assess(state, text, ctx.request.category_hint)
    if state.danger and fresh_danger:
        return ctx.danger_turn(state)
    if result.needs_clarification and state.clarify_count < MAX_CLARIFY:
        state = state.model_copy(update={"clarify_count": state.clarify_count + 1})
        clarify = "clarify_short" if ctx.short else "clarify"
        return ctx.respond(state, [BotMessage(kind="text", text=ctx.bundle[clarify])])
    return _after_description(ctx, state)


def _handle_edit(ctx: _Context, state: ConversationState, text: str) -> TurnResponse:
    state, _, fresh_danger = ctx.assess(state, text, ctx.request.category_hint)
    if fresh_danger:
        return ctx.danger_turn(state)
    return ctx.report_review(state, [])


def _handle_question(ctx: _Context, state: ConversationState, text: str) -> TurnResponse:
    try:
        match = search(text, ctx.language_used, ctx.settings).match
    except Exception as exc:  # noqa: BLE001
        logger.error("question lookup failed with %s", type(exc).__name__)
        match = None
    if match is not None:
        messages = [BotMessage(kind="guidance", title=match.entry.title, text=match.entry.answer)]
    else:
        messages = [ctx.say("no_answer"), ctx.helpline_message()]
    return ctx.offer_turn(state, messages)


def _handle_feeling(ctx: _Context, state: ConversationState, choice: str) -> TurnResponse:
    rank_before = state.severity.rank
    rule = "child_rated_" + choice.removeprefix("feel_")
    state = state.model_copy(
        update={
            "self_rating": choice,
            "asked_feeling": True,
            "rules": list(dict.fromkeys(state.rules + [rule]))[:MAX_STATE_RULES],
        }
    )
    state, _, _ = ctx.assess(state, None)
    if choice == "feel_danger":
        return ctx.danger_turn(state)
    messages: list[BotMessage] = []
    if choice in ("feel_little", "feel_lot") and rank_before > _RATING_RANK[choice]:
        messages.append(ctx.say("feeling_higher"))
    return ctx.next_question(state, messages)


def _handle_now(ctx: _Context, state: ConversationState, choice: str) -> TurnResponse:
    answer = {"yes": True, "no": False, "not_sure": None}[choice]
    state = state.model_copy(update={"happening_now": answer, "asked_now": True})
    state, _, _ = ctx.assess(state, None)
    return ctx.next_question(state, [])


def _handle_who(ctx: _Context, state: ConversationState, choice: str) -> TurnResponse:
    state = state.model_copy(update={"alleged_role": choice, "asked_who": True})
    state, _, _ = ctx.assess(state, None)
    messages: list[BotMessage] = []
    if state.external_only and not state.external_noted:
        messages.append(ctx.say("external_notice"))
        state = state.model_copy(update={"external_noted": True})
    return ctx.next_question(state, messages)


def _handle_offer(ctx: _Context, state: ConversationState, choice: str) -> TurnResponse:
    if choice == "talk_to_person":
        return ctx.offer_turn(state, [ctx.helpline_message()])
    if choice == "keep_proof":
        return ctx.offer_turn(state, _proof_messages(ctx))
    if choice == "just_information":
        return ctx.respond(state.model_copy(update={"step": "ask_question"}), [ctx.say("ask_question")])
    if choice == "report_privately":
        return ctx.report_review(state, [])
    return ctx.respond(state.model_copy(update={"step": "done"}), [ctx.say("closing")])


def _proof_messages(ctx: _Context) -> list[BotMessage]:
    kb = load_knowledge_base(ctx.language_used)
    entry = next((e for e in kb.entries if e.id == EVIDENCE_ENTRY_ID), None) if kb else None
    if entry is not None:
        return [BotMessage(kind="guidance", title=entry.title, text=entry.answer)]
    actions = ctx.bundle["safe_actions"]
    return [BotMessage(kind="list", title=ctx.prompt("safe_actions_title"), items=[a["text"] for a in actions])]


def _handle_report(ctx: _Context, state: ConversationState, choice: str) -> TurnResponse:
    if choice == "edit":
        return ctx.respond(state.model_copy(update={"step": "edit"}), [ctx.say("edit_prompt")])
    if choice == "not_now":
        return ctx.offer_turn(state, [])
    state = state.model_copy(update={"step": "done"})
    result = _result_from_state(state)
    draft = CaseDraft(
        severity=state.severity,
        category=state.category,
        channel=ctx.request.channel,
        language=ctx.request.language,
        external_only=state.external_only,
        human_review=result.human_review,
        summary=" ".join(state.narrative),
        allowed_routes=build_routing(result).allowed_routes,
        consent_confirmed=True,
    )
    return ctx.respond(state, [ctx.say("report_ready")], case_draft=draft)


def _handle_danger_check(ctx: _Context, state: ConversationState, choice: str) -> TurnResponse:
    if choice == "safe_yes":
        return ctx.respond(state.model_copy(update={"step": "offer"}), [ctx.say("danger_safe")])
    return ctx.respond(state, [ctx.say("danger_unsafe"), ctx.helpline_message(), ctx.say("danger_check")])


_CHOICE_HANDLERS = {
    "ask_feeling": _handle_feeling,
    "ask_now": _handle_now,
    "ask_who": _handle_who,
    "offer": _handle_offer,
    "report_review": _handle_report,
    "danger_check": _handle_danger_check,
}
_TEXT_HANDLERS = {
    "describe": _handle_describe,
    "ask_question": _handle_question,
    "edit": _handle_edit,
}


def _digit_choice(text: str, options: tuple[str, ...]) -> str | None:
    """Let a child answer a numbered menu by typing its number."""
    if text.isdigit() and 1 <= int(text) <= len(options):
        return options[int(text) - 1]
    return None


def take_turn(request: TurnRequest, settings: Settings) -> TurnResponse:
    ctx = _Context(request, settings)
    state = request.state or ConversationState()
    text, choice = request.text, request.choice

    if request.state is None and text is None and choice is None:
        return ctx.respond(state, [ctx.say("welcome")])
    if state.step == "done":
        return ctx.respond(state, [ctx.say("closing")])

    if text is not None:
        fresh = safe_triage(text, language=request.language)
        if fresh.danger and state.step != "danger_check":
            state, _, _ = ctx.assess(state, text, request.category_hint)
            return ctx.danger_turn(state)

    options = _STEP_CHOICES.get(state.step)
    if options is None:
        if text is None:
            return ctx.respond(state, [ctx.say("please_choose")])
        return _TEXT_HANDLERS[state.step](ctx, state, text)

    if text is not None:
        choice = _digit_choice(text, options)
        if choice is None:
            state, _, _ = ctx.assess(state, text)
            return ctx.respond(state, [ctx.say("please_choose")])
    if choice not in options:
        return ctx.respond(state, [ctx.say("please_choose")])
    return _CHOICE_HANDLERS[state.step](ctx, state, choice)
