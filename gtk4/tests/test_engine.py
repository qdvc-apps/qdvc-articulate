"""Tests of the llama.cpp engine through the native library, with the tiny
random model from tools/make_test_model.py. Skipped unless both exist:

    tools/build-native.sh && python3 tools/make_test_model.py
    python3 -m unittest tests.test_engine
"""

import os
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qdvc import llm  # noqa: E402
from qdvc.ai import (AIReviewer, AIReviewOptions, Cancelled, CancelToken, JSON_GRAMMAR, PromptFormat,  # noqa: E402
                     ReviewCache)
from qdvc.model import CheckSettings  # noqa: E402

MODEL = Path(os.environ.get("QDVC_TEST_GGUF", ROOT / "build" / "test-model.gguf"))


@unittest.skipUnless(llm.is_available() and MODEL.is_file(), "needs build/native and build/test-model.gguf")
class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = llm.LlamaEngine()
        cls.info = cls.engine.load(str(MODEL), llm.LlamaConfig(context_length=4096))

    @classmethod
    def tearDownClass(cls):
        cls.engine.unload()

    def test_model_info(self):
        self.assertEqual(self.info.architecture, "llama")
        self.assertEqual(self.info.context_length, 4096)
        self.assertEqual(PromptFormat.AUTOMATIC.resolved(self.info.chat_template, self.info.architecture),
                         PromptFormat.CHATML)

    def test_grammar_forces_the_json_shape(self):
        out = self.engine.generate("<|im_start|>system\nCheck.<|im_end|>\n<|im_start|>user\nTEXT:\n",
                                   "Hello.<|im_end|>\n<|im_start|>assistant\n", JSON_GRAMMAR, 64)
        self.assertTrue(out.lstrip().startswith("{"), out)

    def test_review_reuses_the_prefix_and_the_cache(self):
        reviewer = AIReviewer(self.engine, ReviewCache())
        text = "This paragraph is long enough to stand on its own as a chunk of text for the model.\n\n" * 2
        options = AIReviewOptions(PromptFormat.CHATML, self.info.identifier, max_output_tokens=48)
        progress = list(reviewer.review(text, CheckSettings(), options))
        self.assertEqual([(p.completed, p.total, p.from_cache) for p in progress], [(1, 2, False), (2, 2, True)])

    def test_cancellation(self):
        token = CancelToken()
        threading.Timer(0.05, token.cancel).start()
        with self.assertRaises(Cancelled):
            self.engine.generate("a", "b", None, 3000, token)

    def test_errors(self):
        with self.assertRaisesRegex(llm.LlamaError, "too long"):
            self.engine.generate("a", "b " * 5000, None, 100)
        with self.assertRaisesRegex(llm.LlamaError, "grammar"):
            self.engine.generate("a", "b", "root ::= (", 10)


if __name__ == "__main__":
    unittest.main()
