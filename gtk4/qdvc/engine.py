"""The single AI engine shared by every tab: a port of the macOS edition's
ModelManager. It owns the llama.cpp engine and the in-memory review cache,
loads the model the user chose on a worker thread, and runs reviews.

Toolkit-independent: `run_in_thread(work, done)` and `post(fn)` are given by
the front-end (GLib there, synchronous in the tests).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

from . import llm
from .ai import AIReviewer, AIReviewOptions, CancelToken, PromptFormat, ReviewCache
from .model import CheckSettings


class ModelState(Enum):
    NOT_COMPILED_IN = "not-compiled-in"
    NO_MODEL = "no-model"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"


@dataclass
class Status:
    state: ModelState
    detail: str = ""          # the file being loaded, or the failure
    info: llm.ModelInfo | None = None


class ModelManager:
    def __init__(self, prefs, run_in_thread, engine=None, available=None):
        self.prefs = prefs
        self.run_in_thread = run_in_thread
        self.engine = engine or llm.LlamaEngine()
        self.cache = ReviewCache()
        self._available = llm.is_available() if available is None else available
        self.status = Status(ModelState.NO_MODEL if self._available else ModelState.NOT_COMPILED_IN)
        self._listeners: list = []
        self._load_generation = 0

    def connect(self, fn) -> None:
        self._listeners.append(fn)

    def disconnect(self, fn) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    def _set(self, status: Status) -> None:
        self.status = status
        for fn in list(self._listeners):
            fn(status)

    @property
    def available(self) -> bool:
        return self._available

    @property
    def is_ready(self) -> bool:
        return self.status.state is ModelState.READY

    @property
    def info(self) -> llm.ModelInfo | None:
        return self.status.info if self.is_ready else None

    @property
    def resolved_format(self) -> PromptFormat | None:
        info = self.info
        if info is None:
            return None
        return self.prefs.llama.prompt_format.resolved(info.chat_template, info.architecture)

    @property
    def not_ready_message(self) -> str:
        s = self.status.state
        if s is ModelState.NOT_COMPILED_IN:
            return llm.unavailable_reason() or llm.NOT_COMPILED_IN
        if s is ModelState.NO_MODEL:
            return "No AI model selected. Choose a GGUF file in Preferences › AI Model."
        if s is ModelState.LOADING:
            return "The AI model is still loading."
        if s is ModelState.FAILED:
            return self.status.detail
        return ""

    # --- selecting and loading ----------------------------------------------------------

    def set_model(self, path: str) -> None:
        """Remembers a GGUF the user chose (through the file chooser portal, whose path stays valid
        across launches), then loads it."""
        self.prefs.set_model_path(path)
        self.load()

    def load(self) -> None:
        if not self._available:
            self._set(Status(ModelState.NOT_COMPILED_IN))
            return
        path = self.prefs.model_path
        if not path:
            self._set(Status(ModelState.NO_MODEL))
            return
        if not os.path.isfile(path):
            self._set(Status(ModelState.FAILED, "The saved model file could not be found. Choose it again in "
                                                "Preferences › AI Model."))
            return
        llama = self.prefs.llama
        config = llm.LlamaConfig(context_length=llama.context_length, threads=llama.threads)
        self._load_generation += 1
        generation = self._load_generation
        name = os.path.basename(path)
        self._set(Status(ModelState.LOADING, name))

        def work():
            try:
                return self.engine.load(path, config), None
            except llm.LlamaError as e:
                return None, str(e)

        def done(result):
            info, error = result
            if generation != self._load_generation:
                return  # unloaded or reloaded meanwhile
            self.cache.clear()
            self._set(Status(ModelState.READY, name, info) if info else Status(ModelState.FAILED, error))
        self.run_in_thread(work, done)

    def unload(self) -> None:
        self._load_generation += 1
        self.run_in_thread(self.engine.unload, lambda _r: None)
        self._set(Status(ModelState.NO_MODEL if self._available else ModelState.NOT_COMPILED_IN))

    def forget(self) -> None:
        """Unloads the model and forgets the file."""
        self.unload()
        self.prefs.set_model_path(None)

    def clear_cache(self) -> None:
        self.cache.clear()

    # --- reviewing ------------------------------------------------------------------------

    def review(self, text: str, check: CheckSettings, cancel: CancelToken):
        """A generator of ReviewProgress (to run on a worker thread), or None when not ready."""
        info, fmt = self.info, self.resolved_format
        if info is None or fmt is None:
            return None
        llama = self.prefs.llama
        self.engine.configure(llama.temperature, llama.reuse_prompt_cache)
        options = AIReviewOptions(format=fmt, model_identifier=info.identifier,
                                  max_output_tokens=llama.max_output_tokens, max_chunk_length=llama.chunk_length)
        return AIReviewer(self.engine, self.cache).review(text, check, options, cancel)
