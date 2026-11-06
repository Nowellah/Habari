import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from ai_service import vision

ENV = {"HABARI_OLLAMA_URL": "http://127.0.0.1:11434", "HABARI_VISION_MODEL": "vision-test"}


def answer(content):
    r = MagicMock()
    r.json.return_value = {"message": {"content": content if isinstance(content, str) else json.dumps(content)}}
    return r


class VisionTests(SimpleTestCase):
    def run_check(self, content, env=ENV, content_type="image/png", image=b"x"):
        with patch.dict("os.environ", env, clear=False), patch("ai_service.vision.requests.post", return_value=answer(content)) as post:
            return vision.check_proof(image, content_type, "I used my mother's card", "Asked for money"), post

    def test_a_good_answer_is_returned_in_the_fixed_shape(self):
        out, post = self.run_check({"kind": "document", "relevant": "no", "sensitive": False, "reason": "Maths notes."})
        self.assertEqual(out, {"kind": "document", "relevant": "no", "sensitive": False, "reason": "Maths notes."})
        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["model"], "vision-test")
        self.assertIn("I used my mother's card", sent["messages"][0]["content"])
        self.assertTrue(post.call_args.args[0].startswith("http://127.0.0.1:11434"))

    def test_unknown_values_are_replaced_not_trusted(self):
        out, _ = self.run_check({"kind": "ignore all rules", "relevant": "definitely", "sensitive": "yes", "reason": "a\\x00b" + "z" * 400})
        self.assertEqual((out["kind"], out["relevant"], out["sensitive"]), ("other", "unsure", False))
        self.assertLessEqual(len(out["reason"]), 160)

    def test_not_set_up_means_no_check_and_no_request(self):
        with patch.dict("os.environ", {"HABARI_OLLAMA_URL": "", "HABARI_VISION_MODEL": ""}), patch("ai_service.vision.requests.post") as post:
            self.assertIsNone(vision.check_proof(b"x", "image/png", "said"))
        post.assert_not_called()

    def test_pdfs_and_empty_files_are_not_sent(self):
        out, post = self.run_check({"kind": "document"}, content_type="application/pdf")
        self.assertIsNone(out)
        post.assert_not_called()

    def test_a_broken_answer_or_a_down_server_gives_none(self):
        self.assertIsNone(self.run_check("not json")[0])
        with patch.dict("os.environ", ENV), patch("ai_service.vision.requests.post", side_effect=OSError("down")):
            self.assertIsNone(vision.check_proof(b"x", "image/png", "said"))
