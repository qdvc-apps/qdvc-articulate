"""Open documents, drafts and the restored session: the GNOME counterpart of
the macOS edition's document autosaving.

On macOS each document autosaves with versions. Here, as in GNOME Text
Editor, unsaved work is kept as a draft in
$XDG_STATE_HOME/qdvc-articulate/drafts/ (in the Flatpak, under
~/.var/app/qdvc.articulate.gtk4app/), written a moment after each change and
on quit, and the open tabs come back at the next launch, unsaved changes
included. A document is saved to its own file only when you save it.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import yamlio as Y
from .documents import read_text_file, write_text_file
from .preferences import state_dir


@dataclass
class Document:
    """One tab's file: where it lives and what was last saved (to tell whether it is modified)."""
    path: str | None = None
    saved_text: str = ""
    line_ending: str = "\n"
    draft_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    #: For an untitled document: its title and suggested file name (an imported file's name).
    name: str | None = None

    @property
    def title(self) -> str:
        return os.path.basename(self.path) if self.path else (self.name or "Untitled Document")

    @property
    def suggested_name(self) -> str:
        return os.path.basename(self.path) if self.path else (self.name or "Untitled Document.txt")

    def is_modified(self, text: str) -> bool:
        return text != self.saved_text

    @classmethod
    def open(cls, path: str) -> tuple["Document", str]:
        text, ending = read_text_file(path)
        return cls(path=path, saved_text=text, line_ending=ending), text

    def save(self, text: str, path: str | None = None) -> None:
        target = path or self.path
        if not target:
            raise ValueError("no file to save to")
        write_text_file(target, text, self.line_ending)
        self.path = target
        self.saved_text = text


@dataclass
class RestoredTab:
    document: Document
    text: str
    cursor: int = 0


class SessionStore:
    def __init__(self, directory: Path | None = None):
        self.directory = directory or state_dir()
        self.drafts = self.directory / "drafts"
        self.file = self.directory / "session.yml"

    def write_draft(self, doc: Document, text: str) -> None:
        """Keeps unsaved work (or removes the draft when there is none)."""
        p = self.drafts / f"{doc.draft_id}.txt"
        try:
            if doc.is_modified(text) and (doc.path or text.strip()):
                self.drafts.mkdir(parents=True, exist_ok=True)
                write_text_file(p, text)
            elif p.exists():
                p.unlink()
        except OSError:
            pass

    def discard_draft(self, doc: Document) -> None:
        try:
            (self.drafts / f"{doc.draft_id}.txt").unlink()
        except OSError:
            pass

    def save(self, tabs: list[tuple[Document, str, int]], active: int) -> None:
        """tabs: (document, current text, cursor offset)."""
        entries = []
        keep = set()
        for doc, text, cursor in tabs:
            self.write_draft(doc, text)
            has_draft = (self.drafts / f"{doc.draft_id}.txt").exists()
            if not doc.path and not has_draft:
                continue  # an empty untitled tab is not worth restoring
            keep.add(f"{doc.draft_id}.txt")
            pairs = [("draft", Y.s(doc.draft_id)), ("cursor", Y.num(cursor)),
                     ("crlf", Y.flag(doc.line_ending == "\r\n"))]
            if doc.path:
                pairs.insert(0, ("path", Y.s(doc.path)))
            elif doc.name:
                pairs.insert(0, ("name", Y.s(doc.name)))
            entries.append(Y.mapping(pairs))
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            write_text_file(self.file, Y.emit(Y.mapping([("active", Y.num(max(0, active))),
                                                         ("tabs", Y.Sequence(entries))])))
            for p in self.drafts.glob("*.txt") if self.drafts.is_dir() else []:
                if p.name not in keep:
                    p.unlink()
        except OSError:
            pass

    def load(self) -> tuple[list[RestoredTab], int]:
        try:
            doc = Y.parse(self.file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, Y.YAMLError):
            return [], 0
        tabs: list[RestoredTab] = []
        node = doc.get("tabs")
        for entry in node.items if node is not None else []:
            path = entry.get("path").string if entry.get("path") is not None else None
            draft_id = entry.get("draft").string if entry.get("draft") is not None else None
            cursor = entry.get("cursor").int if entry.get("cursor") is not None else 0
            crlf = entry.get("crlf").bool if entry.get("crlf") is not None else False
            draft = self.drafts / f"{draft_id}.txt" if draft_id else None
            saved = ""
            if path and os.path.isfile(path):
                try:
                    saved, ending = read_text_file(path)
                    crlf = ending == "\r\n"
                except OSError:
                    path = None
            elif path:
                path = None  # the file has gone: keep the draft as an untitled document
            try:
                text = read_text_file(draft)[0] if draft and draft.is_file() else None
            except OSError:
                text = None
            if text is None and path is None:
                continue
            name = entry.get("name").string if entry.get("name") is not None else None
            d = Document(path=path, saved_text=saved, line_ending="\r\n" if crlf else "\n",
                         draft_id=draft_id or uuid.uuid4().hex, name=name)
            tabs.append(RestoredTab(d, saved if text is None else text, cursor or 0))
        active = doc.get("active").int if doc.get("active") is not None else 0
        return tabs, min(max(active or 0, 0), max(len(tabs) - 1, 0))
