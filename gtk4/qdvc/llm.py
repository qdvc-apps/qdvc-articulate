"""The llama.cpp engine, through ctypes and the small native library in
native/ (libqdvc-articulate-llama.so): the counterpart of the macOS
edition's ArticulateLLM/LlamaEngine.swift.

The native library is compiled against the llama.cpp in vendor/ (in the
Flatpak, by the manifest; from a checkout, by tools/build-native.sh). Without
it the app runs with the rules and the spelling checker, and the AI review
says how to add the engine.
"""

from __future__ import annotations

import ctypes
import os
import random
import threading
from dataclasses import dataclass
from pathlib import Path

from .ai import Cancelled, CancelToken

LIBRARY_NAME = "libqdvc-articulate-llama.so"
API_VERSION = 1  # native/articulate_llama.h: QAL_API_VERSION

QAL_OK, QAL_CANCELLED = 0, 1

NOT_COMPILED_IN = ("This build has no AI engine. Put a llama.cpp checkout into gtk4/vendor/llama.cpp and run "
                   "scripts/build-app.sh --install again; see vendor/README.md.")


class LlamaError(Exception):
    pass


@dataclass(frozen=True)
class LlamaConfig:
    context_length: int = 8192
    #: Layers to offload to a GPU. The Flatpak build is CPU-only, so this has no effect there.
    gpu_layers: int = 0
    #: 0 = automatic (the number of CPUs less two).
    threads: int = 0
    batch_size: int = 1024


@dataclass(frozen=True)
class ModelInfo:
    file_name: str
    description: str
    architecture: str | None
    chat_template: str | None
    size_bytes: int
    parameter_count: int
    trained_context_length: int
    context_length: int

    @property
    def identifier(self) -> str:
        """Stable identifier used to key the review cache."""
        return f"{self.file_name}#{self.size_bytes}"


def _candidates() -> list[Path]:
    here = Path(__file__).resolve().parent.parent
    paths = []
    if os.environ.get("QDVC_ARTICULATE_LLAMA_LIB"):
        paths.append(Path(os.environ["QDVC_ARTICULATE_LLAMA_LIB"]))
    paths += [Path("/app/lib") / LIBRARY_NAME, here / "build" / "native" / LIBRARY_NAME]
    return paths


_lib = None
_lib_error: str | None = None
_lib_lock = threading.Lock()


def library():
    """The native library, loaded once, or None (see `unavailable_reason`)."""
    global _lib, _lib_error
    with _lib_lock:
        if _lib is not None or _lib_error is not None:
            return _lib
        for path in _candidates():
            if not path.is_file():
                continue
            try:
                lib = ctypes.CDLL(str(path))
            except OSError as e:
                _lib_error = f"The AI engine ({path}) could not be loaded: {e}"
                return None
            _declare(lib)
            if lib.qal_api_version() != API_VERSION:
                _lib_error = (f"The AI engine ({path}) has interface version {lib.qal_api_version()}, but this "
                              f"version of the app needs {API_VERSION}. Rebuild it.")
                return None
            _lib = lib
            return lib
        _lib_error = NOT_COMPILED_IN
        return None


def is_available() -> bool:
    return library() is not None


def unavailable_reason() -> str:
    library()
    return _lib_error or ""


def _declare(lib) -> None:
    c = ctypes
    lib.qal_api_version.restype = c.c_int
    lib.qal_system_info.restype = c.c_char_p
    lib.qal_load.restype = c.c_void_p
    lib.qal_load.argtypes = [c.c_char_p, c.c_int, c.c_int, c.c_int, c.c_int, c.c_char_p, c.c_int]
    lib.qal_free.argtypes = [c.c_void_p]
    lib.qal_meta.restype = c.c_int
    lib.qal_meta.argtypes = [c.c_void_p, c.c_char_p, c.c_char_p, c.c_int]
    for name in ("qal_size", "qal_n_params"):
        getattr(lib, name).restype = c.c_ulonglong
        getattr(lib, name).argtypes = [c.c_void_p]
    for name in ("qal_n_ctx_train", "qal_n_ctx"):
        getattr(lib, name).restype = c.c_int
        getattr(lib, name).argtypes = [c.c_void_p]
    lib.qal_generate.restype = c.c_int
    lib.qal_generate.argtypes = [c.c_void_p, c.c_char_p, c.c_char_p, c.c_char_p, c.c_int, c.c_float, c.c_int,
                                 c.c_uint, c.POINTER(c.c_int), c.POINTER(c.c_void_p), c.c_char_p, c.c_int]
    lib.qal_free_string.argtypes = [c.c_void_p]


def _first_line(err) -> str:
    """The message from the native library, with only the first line of llama.cpp's own log."""
    text = err.value.decode("utf-8", "replace").strip()
    head, _, rest = text.partition(" (")
    detail = rest.split("\n")[0].rstrip(")") if rest else ""
    return f"{head} ({detail})" if detail else head


def system_info() -> str:
    lib = library()
    return lib.qal_system_info().decode("utf-8", "replace") if lib else ""


class LlamaEngine:
    """One llama.cpp model and context. Calls into the library release the GIL (ctypes does), so a
    review on a worker thread leaves the window responsive. One generation at a time (a lock)."""

    def __init__(self):
        self._handle: int | None = None
        self._lock = threading.Lock()
        self.model_info: ModelInfo | None = None
        self.temperature = 0.0
        self.reuse_prefix = True

    def configure(self, temperature: float, reuse_prompt_cache: bool) -> None:
        """Sampling options that can change without reloading the model."""
        self.temperature = max(0.0, float(temperature))
        self.reuse_prefix = bool(reuse_prompt_cache)

    def load(self, path: str, config: LlamaConfig) -> ModelInfo:
        lib = library()
        if lib is None:
            raise LlamaError(unavailable_reason())
        name = os.path.basename(path)
        if not os.path.isfile(path):
            raise LlamaError(f"“{name}” could not be found. Choose it again in Preferences › AI Model.")
        with self._lock:
            self._unload_locked()
            err = ctypes.create_string_buffer(1024)
            handle = lib.qal_load(os.fsencode(path), config.context_length, config.gpu_layers, config.threads,
                                  config.batch_size, err, len(err))
            if not handle:
                raise LlamaError(f"Could not load “{name}”. {_first_line(err)}.")
            self._handle = handle

            def meta(what: str) -> str | None:
                buf = ctypes.create_string_buffer(65536 if what == "template" else 512)
                n = lib.qal_meta(handle, what.encode(), buf, len(buf))
                return buf.value.decode("utf-8", "replace") if n >= 0 else None

            self.model_info = ModelInfo(
                file_name=name,
                description=meta("desc") or name,
                architecture=meta("arch"),
                chat_template=meta("template"),
                size_bytes=lib.qal_size(handle),
                parameter_count=lib.qal_n_params(handle),
                trained_context_length=lib.qal_n_ctx_train(handle),
                context_length=lib.qal_n_ctx(handle),
            )
            return self.model_info

    def unload(self) -> None:
        with self._lock:
            self._unload_locked()

    def _unload_locked(self) -> None:
        if self._handle:
            library().qal_free(self._handle)
        self._handle = None
        self.model_info = None

    @property
    def is_loaded(self) -> bool:
        return self._handle is not None

    def generate(self, prefix: str, body: str, grammar: str | None, max_tokens: int,
                 cancel: CancelToken | None = None) -> str:
        lib = library()
        flag = ctypes.c_int(0)
        if cancel is not None:
            cancel.on_cancel(lambda: setattr(flag, "value", 1))
        with self._lock:
            if not self._handle:
                raise LlamaError("No model is loaded.")
            out = ctypes.c_void_p()
            err = ctypes.create_string_buffer(1024)
            rc = lib.qal_generate(self._handle, prefix.encode("utf-8"), body.encode("utf-8"),
                                  grammar.encode("utf-8") if grammar else None, max_tokens, self.temperature,
                                  1 if self.reuse_prefix else 0, random.randrange(1 << 32), ctypes.byref(flag),
                                  ctypes.byref(out), err, len(err))
            if rc == QAL_CANCELLED:
                raise Cancelled()
            if rc != QAL_OK:
                raise LlamaError(_first_line(err) + ".")
            try:
                return ctypes.string_at(out.value).decode("utf-8", "replace") if out.value else ""
            finally:
                lib.qal_free_string(out.value)
