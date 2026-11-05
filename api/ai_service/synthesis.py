"""Case synthesis for officers: a short summary, a timeline and the key details.

The summary is extractive: it only reuses the child's own sentences, so it cannot
invent facts. Details (handles, numbers, links, amounts, dates, platforms) come
from regular expressions, which are predictable and easy to check.
An instruction model can replace the summary later; the entities stay rule-based.
"""
import re

from ai_service import lexicon_engine

PLATFORMS = ["instagram", "tiktok", "whatsapp", "snapchat", "facebook", "telegram", "twitter", "x.com",
             "linkedin", "youtube", "discord", "roblox"]
DATE_WORDS = ["today", "yesterday", "tonight", "tomorrow", "last night", "last week", "this morning",
              "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

HANDLE = re.compile(r"(?<![\w.@])@[A-Za-z0-9_.]{2,30}")
PHONE = re.compile(r"(?<!\d)(?:\+?256|0)[\s-]?7\d(?:[\s-]?\d){7}(?!\d)")
URL = re.compile(r"https?://[^\s<>\"']+")
AMOUNT = re.compile(r"(?:(?:ugx|shs?)\s*(\d{1,3}(?:,\d{3})+|\d+))|(?:(\d{1,3}(?:,\d{3})+|\d+)\s*(k\b|shillings|ugx|/=|shs?\b))",
                    re.I)
NUM_DATE = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")
SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")


def _phone(raw):
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0"):
        digits = "256" + digits[1:]
    return "+" + digits


def extract_entities(text):
    low = text.lower()
    amounts = []
    for m in AMOUNT.finditer(text):
        number = m.group(1) or m.group(2)
        value = int(number.replace(",", ""))
        if (m.group(3) or "").lower() == "k":
            value *= 1000
        amounts.append(value)
    dates = [w for w in DATE_WORDS if re.search(rf"\b{w}\b", low)] + NUM_DATE.findall(text)
    return {
        "handles": sorted({h.rstrip(".") for h in HANDLE.findall(text)}),
        "phones": sorted({_phone(p) for p in PHONE.findall(text)}),
        "urls": sorted({u.rstrip(".,)") for u in URL.findall(text)}),
        "amounts_ugx": sorted(set(amounts)),
        "dates": dates,
        "platforms": [p.replace(".com", "") for p in PLATFORMS if re.search(rf"\b{re.escape(p)}\b", low)],
    }


def summarise(messages, max_lines=3):
    msgs = sorted([m for m in messages if (m.get("text") or "").strip()], key=lambda m: m.get("at") or "")
    if not msgs:
        return {"summary": "", "timeline": [], "entities": extract_entities(""), "method": "extractive"}
    sentences = []
    for mi, m in enumerate(msgs):
        for s in SENTENCE.findall(m["text"]):
            s = s.strip()
            if len(s) >= 3:
                sentences.append((mi, s))
    scored = []
    for order, (mi, s) in enumerate(sentences):
        flags, floor = lexicon_engine.match(s)
        details = sum(len(v) for v in extract_entities(s).values())
        scored.append((floor * 10 + len(flags) * 2 + details, order, s))
    keep = {0}  # the opening sentence sets the scene
    for score, order, _ in sorted(scored, key=lambda x: (-x[0], x[1])):
        if len(keep) >= max_lines:
            break
        if score > 0:
            keep.add(order)
    lines = [scored[o][2][:200] for o in sorted(keep)]
    full = " ".join(m["text"] for m in msgs)
    return {
        "summary": "\n".join("- " + line for line in lines),
        "timeline": [{"at": m.get("at") or "", "text": m["text"][:120]} for m in msgs],
        "entities": extract_entities(full),
        "method": "extractive",
    }
