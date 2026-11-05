// Habari extension popup: pick, optional words, optional screenshot, send.
// Talks to the same gateway as every other channel: /api/channel/extension.
const SERVER_DEFAULT = "http://localhost:8000";
const PICKS = [
  ["1", "I am in danger or I want to hurt myself"],
  ["2", "Someone is asking for pictures, money or secrets"],
  ["3", "An adult in charge is hurting me"],
  ["4", "Someone is being mean or fake"],
  ["5", "Something upsetting or risky online"],
];

let chosen = null;
let page = { url: "", title: "", selection: "" };

async function senderId() {
  // A random id so the child can follow up from this browser. No name, no account.
  const { senderId } = await chrome.storage.local.get("senderId");
  if (senderId) return senderId;
  const id = "ext-" + crypto.randomUUID();
  await chrome.storage.local.set({ senderId: id });
  return id;
}

async function server() {
  const { server } = await chrome.storage.local.get("server");
  return server || SERVER_DEFAULT;
}

async function post(text, meta) {
  const body = { channel: "extension", sender_id: await senderId(), text, meta };
  const r = await fetch((await server()) + "/api/channel/extension", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error("server said " + r.status);
  return r.json();
}

function showReply(out, base) {
  const box = document.getElementById("reply");
  box.hidden = false;
  box.textContent = out.reply_text;
  if (out.reply_text.startsWith("Call ")) box.classList.add("danger");
  if (out.case_code) {
    const a = document.createElement("a");
    a.href = base + "/status/" + out.case_code;
    a.target = "_blank";
    a.textContent = "\nSee my case " + out.case_code;
    box.appendChild(a);
  }
  document.getElementById("form").hidden = true;
}

async function init() {
  const picksBox = document.getElementById("picks");
  for (const [key, label] of PICKS) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "pick"; b.textContent = label; b.setAttribute("aria-pressed", "false");
    b.addEventListener("click", () => {
      chosen = key;
      picksBox.querySelectorAll(".pick").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
      document.getElementById("send").disabled = false;
    });
    picksBox.appendChild(b);
  }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) page = { url: tab.url || "", title: tab.title || "", selection: "" };
  const { pending } = await chrome.storage.session.get("pending");
  if (pending) {
    page = { ...page, ...pending };
    await chrome.storage.session.remove("pending");
    if (pending.selection) document.getElementById("text").value = pending.selection;
  }
  const platform = detectPlatform(page.url);
  document.getElementById("page").textContent = platform !== "web" ? "From: " + platform : "";

  document.getElementById("form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("send");
    btn.disabled = true; btn.textContent = "Sending…";
    const meta = { url: page.url, title: page.title, platform: detectPlatform(page.url) };
    if (page.selection) meta.selection = page.selection;
    if (document.getElementById("shot").checked) {
      try {
        meta.screenshot = await chrome.tabs.captureVisibleTab(null, { format: "jpeg", quality: 60 });
      } catch (err) { /* no picture: the report still goes */ }
    }
    const base = await server();
    try {
      await post("HELP", meta);
      let out = await post(chosen, meta);
      if (!out.case_code) {  // picks 2 to 5 ask for words; pick 1 is already a case
        const words = document.getElementById("text").value.trim();
        out = await post(words || "0", meta);
      }
      showReply(out, base);
    } catch (err) {
      showReply({ reply_text: "We could not connect. If you are in danger, call 116. It is free." }, base);
    }
  });

  document.getElementById("exit").addEventListener("click", () => window.close());
}

init();
