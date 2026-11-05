(() => {
  "use strict";

  const EXIT_URL = "https://www.google.com/";
  const REQUEST_TIMEOUT_MS = 15000;
  const SMS_LIMIT = 160;
  const DRAFT_NOTE = "Prepared after the child confirmed. Not saved: no case system is connected yet.";
  const OFFLINE_MESSAGE =
    "Sorry, I can't reach the helper right now. If you are in danger, move to a safe place near other people and ask an adult close by to help you now.";
  const PLACEHOLDERS = {
    describe: "Type here. You can say as much or as little as you like.",
    ask_question: "Type your question.",
    edit: "Type what you want to add.",
  };
  const DEFAULT_PLACEHOLDER = "Choose an option above, or type here.";

  const $ = (id) => document.getElementById(id);
  const els = {
    safety: $("safety-check"),
    chat: $("chat"),
    log: $("log"),
    form: $("composer"),
    message: $("message"),
    send: $("send"),
    topics: $("topics"),
    channel: $("channel"),
    language: $("language"),
    staff: $("staff"),
    staffToggle: $("staff-toggle"),
    staffEmpty: $("staff-empty"),
    result: $("result"),
    sev: $("sev"),
    cat: $("cat"),
    facts: $("facts"),
    routes: $("routes"),
    rules: $("rules"),
    raw: $("raw"),
    draft: $("draft"),
    draftNote: $("draft-note"),
  };

  const app = { conversation: null, hint: null, busy: false, escapePressedAt: 0, callShown: false };

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function scrollToEnd() {
    els.log.scrollTop = els.log.scrollHeight;
  }

  function isShortChannel() {
    return els.channel.value !== "chat";
  }

  function addBubble(role, text, extraClass) {
    const bubble = node("div", "bubble " + role + (extraClass ? " " + extraClass : ""), text);
    els.log.appendChild(bubble);
    scrollToEnd();
    return bubble;
  }

  function addBotText(message) {
    const classes = [];
    if (message.kind === "danger") classes.push("danger-bubble");
    if (isShortChannel()) classes.push("sms");
    const bubble = addBubble("bot", message.text, classes.join(" "));
    if (isShortChannel()) {
      bubble.appendChild(node("span", "counter", message.text.length + "/" + SMS_LIMIT + " characters"));
    }
  }

  function addCard(title, subtitle, body, items) {
    const card = node("div", "card");
    if (title) card.appendChild(node("h3", null, title));
    if (subtitle) card.appendChild(node("h4", null, subtitle));
    if (body) card.appendChild(node("p", null, body));
    if (items) {
      const list = node("ul");
      items.forEach((item) => list.appendChild(node("li", null, item)));
      card.appendChild(list);
    }
    els.log.appendChild(card);
  }

  function renderMessages(messages) {
    messages.forEach((message) => {
      if (message.kind === "guidance") {
        addCard("From the Habari guide", message.title, message.text);
      } else if (message.kind === "list") {
        addCard(message.title, null, null, message.items);
      } else {
        addBotText(message);
      }
    });
  }

  function addCallButton(data) {
    const severity = data.assessment.severity;
    if ((severity !== "S3" && severity !== "S4") || !data.helpline || isShortChannel()) return;
    if (app.callShown && data.state.step !== "danger_check") return;
    app.callShown = true;
    const link = node("a", "call", "Call " + data.helpline);
    link.href = "tel:" + data.helpline.replace(/[^0-9+]/g, "");
    els.log.appendChild(link);
  }

  function clearOptions() {
    els.log.querySelectorAll(".options").forEach((element) => element.remove());
  }

  function renderChoices(data) {
    if (!data.choices.length) return;
    if (isShortChannel()) {
      const menu = addBubble("bot", data.menu_text, "sms");
      menu.appendChild(node("span", "counter", "Reply with a number"));
      return;
    }
    const wrapper = node("div", "options");
    data.choices.forEach((choice) => {
      const button = node("button", "option", choice.label);
      button.type = "button";
      button.addEventListener("click", () => takeTurn({ choice: choice.id }, choice.label));
      wrapper.appendChild(button);
    });
    els.log.appendChild(wrapper);
  }

  function renderStaff(data) {
    const assessment = data.assessment;
    els.staffEmpty.hidden = true;
    els.result.hidden = false;
    els.sev.textContent = assessment.severity;
    els.sev.className = "sev " + assessment.severity;
    els.cat.textContent = assessment.category.replace(/_/g, " ");

    const rating = data.state.self_rating ? data.state.self_rating.replace("feel_", "") : "not asked yet";
    const facts = [
      ["Step", data.state.step.replace(/_/g, " ")],
      ["Child's own rating", rating],
      ["Confidence", assessment.confidence],
      ["Human review", assessment.human_review ? "Required" : "Not required"],
      ["Family or school", assessment.external_only ? "Kept out (external only)" : "May be involved if the child agrees"],
      ["Human decision", data.routing.human_decision_required ? "Required, danger to life" : "No"],
      ["Reply language", data.language_used + (data.needs_native_review ? " (fallback, needs native review)" : "")],
      ["Helpline", data.helpline_configured ? "Configured" : "Not configured"],
      ["Reply text", data.content_review_status],
    ];
    els.facts.replaceChildren();
    facts.forEach(([name, value]) => {
      els.facts.appendChild(node("dt", null, name));
      els.facts.appendChild(node("dd", null, value));
    });

    els.routes.replaceChildren();
    data.routing.allowed_routes.forEach((route) => els.routes.appendChild(node("li", null, route.replace(/_/g, " "))));
    els.rules.replaceChildren();
    assessment.matched_rules.forEach((rule) => els.rules.appendChild(node("li", null, rule)));
    els.raw.textContent = JSON.stringify(data, null, 2);

    if (data.case_draft) {
      els.draft.hidden = false;
      els.draft.textContent = JSON.stringify(data.case_draft, null, 2);
      els.draftNote.textContent = DRAFT_NOTE;
    }
  }

  function updateComposer(data) {
    const step = data.state.step;
    els.topics.hidden = step !== "describe" || data.state.narrative.length > 0;
    els.message.placeholder = PLACEHOLDERS[step] || DEFAULT_PLACEHOLDER;
    els.message.disabled = data.ended;
    els.send.disabled = data.ended;
  }

  function clearHint() {
    app.hint = null;
    els.topics.querySelectorAll(".chip").forEach((chip) => chip.setAttribute("aria-pressed", "false"));
  }

  async function takeTurn(input, userLabel) {
    if (app.busy) return;
    app.busy = true;
    els.send.disabled = true;
    clearOptions();
    if (userLabel) addBubble("user", userLabel);

    const payload = Object.assign({ language: els.language.value, channel: els.channel.value }, input);
    if (app.conversation) payload.state = app.conversation;
    if (app.hint && (!app.conversation || app.conversation.step === "describe")) payload.category_hint = app.hint;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const response = await fetch("/api/conversation/turn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error("bad status");
      const data = await response.json();
      app.conversation = data.state;
      renderMessages(data.messages);
      addCallButton(data);
      renderChoices(data);
      renderStaff(data);
      updateComposer(data);
    } catch (error) {
      addBubble("bot", OFFLINE_MESSAGE, "danger-bubble");
    } finally {
      clearTimeout(timer);
      clearHint();
      app.busy = false;
      if (!els.message.disabled) {
        els.send.disabled = false;
        els.message.focus();
      }
    }
  }

  function openChat() {
    els.safety.hidden = true;
    els.chat.hidden = false;
  }

  function quickExit() {
    els.log.replaceChildren();
    els.message.value = "";
    app.conversation = null;
    app.callShown = false;
    window.location.replace(EXIT_URL);
  }

  $("safe-yes").addEventListener("click", () => {
    openChat();
    takeTurn({});
  });

  $("safe-no").addEventListener("click", () => {
    openChat();
    app.hint = "immediate_danger";
    takeTurn({ text: "I need help now" }, "I need help now");
  });

  $("quick-exit").addEventListener("click", quickExit);

  els.channel.addEventListener("change", () => {
    els.message.placeholder = isShortChannel() ? "Type a number or your words." : DEFAULT_PLACEHOLDER;
  });

  els.staffToggle.addEventListener("click", () => {
    const on = els.staff.hidden;
    els.staff.hidden = !on;
    document.body.classList.toggle("staff-on", on);
    els.staffToggle.setAttribute("aria-pressed", String(on));
  });

  els.topics.querySelectorAll(".chip").forEach((chip) => {
    chip.setAttribute("aria-pressed", "false");
    chip.addEventListener("click", () => {
      const selected = chip.getAttribute("aria-pressed") === "true";
      clearHint();
      if (!selected) {
        app.hint = chip.dataset.hint;
        chip.setAttribute("aria-pressed", "true");
      }
    });
  });

  els.form.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = els.message.value.trim();
    if (!text) return;
    els.message.value = "";
    takeTurn({ text }, text);
  });

  els.message.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      els.form.requestSubmit();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const now = Date.now();
    if (now - app.escapePressedAt < 800) quickExit();
    app.escapePressedAt = now;
  });
})();
