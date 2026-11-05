from django.test import TestCase

from channels.telegram import TelegramBot
from core.models import Case


class FakeTelegram:
    """Records what the bot sends instead of calling api.telegram.org."""

    def __init__(self):
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append((url.rsplit("/", 1)[-1], json))

        class R:
            def json(self_inner):
                return {"ok": True}

        return R()

    def sent(self, method):
        return [payload for m, payload in self.calls if m == method]


def text_update(uid, text, chat_id=42):
    return {"update_id": uid, "message": {"message_id": uid, "chat": {"id": chat_id}, "text": text}}


def button_update(uid, data, chat_id=42):
    return {"update_id": uid, "callback_query": {"id": f"cb{uid}", "data": data,
                                                 "message": {"chat": {"id": chat_id}}}}


class TelegramBotTests(TestCase):
    def setUp(self):
        self.tg = FakeTelegram()
        self.bot = TelegramBot("TEST-TOKEN", session=self.tg)

    def test_start_sends_menu_with_five_buttons(self):
        self.bot.handle_update(text_update(1, "/start"))
        msg = self.tg.sent("sendMessage")[-1]
        self.assertEqual(msg["chat_id"], 42)
        self.assertIn("not in trouble", msg["text"])
        keys = [row[0]["callback_data"] for row in msg["reply_markup"]["inline_keyboard"]]
        self.assertEqual(keys, ["1", "2", "3", "4", "5"])

    def test_button_tap_is_answered_and_flow_continues(self):
        self.bot.handle_update(text_update(1, "/start"))
        self.bot.handle_update(button_update(2, "2"))
        self.assertEqual(self.tg.sent("answerCallbackQuery")[-1]["callback_query_id"], "cb2")
        self.assertIn("Tell us what happened", self.tg.sent("sendMessage")[-1]["text"])

    def test_full_report_creates_telegram_case(self):
        self.bot.handle_update(text_update(1, "/start"))
        self.bot.handle_update(button_update(2, "2"))
        self.bot.handle_update(text_update(3, "someone wants my pictures"))
        case = Case.objects.get()
        self.assertEqual(case.channel, "telegram")
        self.assertIn(case.code, self.tg.sent("sendMessage")[-1]["text"])

    def test_reply_without_options_has_no_keyboard(self):
        self.bot.handle_update(text_update(1, "/start"))
        self.bot.handle_update(button_update(2, "2"))
        self.assertNotIn("reply_markup", self.tg.sent("sendMessage")[-1])

    def test_voice_note_gets_a_polite_reply_not_silence(self):
        self.bot.handle_update({"update_id": 5, "message": {"chat": {"id": 42}, "voice": {"file_id": "x"}}})
        self.assertIn("type your message", self.tg.sent("sendMessage")[-1]["text"])

    def test_edited_messages_are_ignored(self):
        self.bot.handle_update({"update_id": 6, "edited_message": {"chat": {"id": 42}, "text": "hi"}})
        self.assertEqual(self.tg.calls, [])

    def test_offset_moves_past_each_update(self):
        self.assertEqual(self.bot.handle_update(text_update(10, "/start")), 11)

    def test_one_bad_update_does_not_stop_the_bot(self):
        with self.assertLogs("channels.telegram", "ERROR"):
            self.assertEqual(self.bot.handle_update({"update_id": 7, "message": {"chat": {}}}), 8)
