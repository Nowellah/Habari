"""Telegram bot adapter, long polling (no public URL or tunnel needed).

Run with:  python manage.py run_telegram   (needs TELEGRAM_TOKEN in .env)
"""
import logging
import time

import requests

from channels.gateway import handle, handle_voice_transcript
from core import ai_client
from core.messages import msg as msg_text

log = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, token, session=requests):
        self.api = f"https://api.telegram.org/bot{token}"
        self.file_api = f"https://api.telegram.org/file/bot{token}"
        self.session = session

    def call(self, method, **payload):
        return self.session.post(f"{self.api}/{method}", json=payload, timeout=10)

    def send(self, chat_id, out):
        payload = {"chat_id": chat_id, "text": out["reply_text"]}
        if out.get("options"):
            payload["reply_markup"] = {"inline_keyboard": [
                [{"text": f'{o["key"]}. {o["label"]}', "callback_data": o["key"]}] for o in out["options"]
            ]}
        self.call("sendMessage", **payload)

    def handle_update(self, u) -> int:
        """Handle one update. Returns the next offset. Never raises."""
        next_offset = u.get("update_id", 0) + 1
        try:
            msg, cq = u.get("message"), u.get("callback_query")
            if cq:
                # Tell Telegram the tap was handled, or the button keeps spinning.
                self.call("answerCallbackQuery", callback_query_id=cq["id"])
                chat_id, text = cq["message"]["chat"]["id"], cq["data"]
            elif msg and msg.get("text"):
                chat_id, text = msg["chat"]["id"], msg["text"]
            elif msg and msg.get("location"):
                chat_id = msg["chat"]["id"]
                loc = msg["location"]
                self.send(chat_id, handle(channel="telegram", sender_id=f"tg:{chat_id}", text="",
                                          location={"lat": loc.get("latitude"), "lon": loc.get("longitude")}))
                return next_offset
            elif msg and (msg.get("voice") or msg.get("audio")):
                chat_id = msg["chat"]["id"]
                heard = self.transcribe(msg.get("voice") or msg.get("audio"))
                if heard is None:  # never ignore a child silently
                    self.call("sendMessage", chat_id=chat_id, text=msg_text("voice_failed"))
                else:
                    self.send(chat_id, handle_voice_transcript("telegram", f"tg:{chat_id}", heard["text"]))
                return next_offset
            elif msg:
                self.call("sendMessage", chat_id=msg["chat"]["id"],
                          text="Thank you. Please type your message, or send /start.")
                return next_offset
            else:
                return next_offset  # edited messages and other update types
            self.send(chat_id, handle(channel="telegram", sender_id=f"tg:{chat_id}", text=text))
        except Exception:
            log.exception("telegram update %s failed", u.get("update_id"))
        return next_offset

    def transcribe(self, voice):
        """Download a voice note from Telegram and turn it into text. None on any failure."""
        try:
            info = self.call("getFile", file_id=voice["file_id"]).json()
            path = info["result"]["file_path"]
            r = self.session.get(f"{self.file_api}/{path}", timeout=30)
            if r.status_code != 200 or not r.content:
                return None
            return ai_client.transcribe(r.content, path.rsplit("/", 1)[-1], None)
        except Exception:
            return None

    def run_forever(self):
        offset = None
        log.info("Telegram bot polling started")
        while True:
            try:
                r = self.session.get(f"{self.api}/getUpdates",
                                     params={"timeout": 30, "offset": offset}, timeout=40).json()
            except (requests.RequestException, ValueError):
                time.sleep(2)  # network blip: retry instead of crashing
                continue
            if not r.get("ok"):
                log.error("Telegram said: %s", r.get("description"))
                time.sleep(5)
                continue
            for u in r.get("result", []):
                offset = self.handle_update(u)
