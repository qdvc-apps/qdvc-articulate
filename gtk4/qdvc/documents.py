"""Reading and writing documents, and importing rich formats as plain text:
the counterpart of the macOS edition's TextDocument.swift and
DocumentImporter.swift.

The macOS edition imports through AppKit's text importers. Here every
format is read by this module with the standard library alone: .docx and
.odt (zipped XML), .rtf (a small reader for the text it carries) and .doc
(Word 97–2003: the OLE compound file, then the text through the piece
table). Like the macOS edition, HTML is not imported: nothing here could
fetch a remote resource, and nothing is ever fetched.
"""

from __future__ import annotations

import os
import re
import struct
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

TEXT_SUFFIXES = (".txt", ".text", ".md", ".markdown")
IMPORT_SUFFIXES = (".docx", ".doc", ".odt", ".rtf")


class DocumentError(Exception):
    """A document that could not be read (the message is for the user)."""


# --- plain text ------------------------------------------------------------------------------

def decode(data: bytes) -> str:
    """UTF-8 (with or without a BOM), UTF-16 with a BOM, else Windows-1252 (as TextDocument.decode)."""
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", "replace")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", "replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", "replace")


def read_text_file(path: str | os.PathLike) -> tuple[str, str]:
    """The text with \\n line breaks, and the file's own line ending ("\\n" or "\\r\\n") to save with."""
    text = decode(Path(path).read_bytes())
    ending = "\r\n" if "\r\n" in text else "\n"
    return text.replace("\r\n", "\n").replace("\r", "\n"), ending


def write_text_file(path: str | os.PathLike, text: str, line_ending: str = "\n") -> None:
    """Writes UTF-8 atomically (a temporary file beside it, then a rename), keeping the file's mode."""
    p = Path(path)
    data = (text.replace("\n", line_ending) if line_ending != "\n" else text).encode("utf-8")
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    try:
        mode = os.stat(p).st_mode & 0o777
    except OSError:
        mode = None
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, p)
    except OSError:
        # The document portal may refuse a sibling file: write in place instead.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        with open(p, "wb") as f:
            f.write(data)


# --- importing ---------------------------------------------------------------------------------

def import_document(path: str | os.PathLike) -> str:
    """The text of a .docx, .doc, .odt, .rtf or plain-text file."""
    p = Path(path)
    suffix = p.suffix.lower()
    try:
        if suffix in TEXT_SUFFIXES:
            return read_text_file(p)[0]
        data = p.read_bytes()
        if suffix == ".docx":
            text = docx_text(data)
        elif suffix == ".odt":
            text = odt_text(data)
        elif suffix == ".rtf":
            text = rtf_text(data)
        elif suffix == ".doc":
            text = doc_text(data)
        else:
            raise DocumentError(f"“{suffix or p.name}” files can’t be imported. Supported: .docx, .doc, .odt, .rtf, "
                               ".txt, .md.")
    except DocumentError:
        raise
    except (OSError, zipfile.BadZipFile, ET.ParseError, KeyError, struct.error, IndexError, ValueError) as e:
        raise DocumentError(f"“{p.name}” could not be read: {e}") from e
    return _tidy(text)


def _tidy(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u2028", "\n").replace("\ufffc", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip("\n") + "\n" if text.strip() else ""


# .docx (Office Open XML)

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"  # XML namespace: a name, never fetched


def docx_text(data: bytes) -> str:
    with zipfile.ZipFile(_bytes_io(data)) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out: list[str] = []

    def walk(el) -> None:
        tag = el.tag
        if tag == _W + "t":
            out.append(el.text or "")
            return
        if tag == _W + "tab":
            out.append("\t")
            return
        if tag in (_W + "br", _W + "cr"):
            out.append("\n")
            return
        if tag == _W + "noBreakHyphen":
            out.append("\u2011")
            return
        if tag in (_W + "delText", _W + "instrText", _W + "del"):
            return
        for child in el:
            walk(child)
        if tag == _W + "p":
            out.append("\n")
        elif tag == _W + "tc":
            out.append("\t")

    body = root.find(_W + "body")
    walk(body if body is not None else root)
    return "".join(out)


# .odt (OpenDocument text)

_TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
_OFFICE = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"


def odt_text(data: bytes) -> str:
    with zipfile.ZipFile(_bytes_io(data)) as z:
        root = ET.fromstring(z.read("content.xml"))
    out: list[str] = []
    skip = {_OFFICE + "annotation", _TEXT + "note", _TEXT + "tracked-changes", _TEXT + "bookmark-ref",
            _TEXT + "sequence-decls"}

    def walk(el) -> None:
        tag = el.tag
        if tag in skip:
            return
        if tag == _TEXT + "s":
            out.append(" " * int(el.get(_TEXT + "c", "1")))
        elif tag == _TEXT + "tab":
            out.append("\t")
        elif tag == _TEXT + "line-break":
            out.append("\n")
        else:
            if el.text:
                out.append(el.text)
            for child in el:
                walk(child)
                if child.tail:
                    out.append(child.tail)
            if tag in (_TEXT + "p", _TEXT + "h"):
                out.append("\n")
            return
        # (text:s, text:tab and text:line-break carry no text of their own; their tails are added by the parent.)

    body = root.find(_OFFICE + "body")
    walk(body if body is not None else root)
    return "".join(out)


# .rtf

_RTF_TOKEN = re.compile(rb"\\([a-zA-Z]+)(-?\d+)? ?|\\'([0-9a-fA-F]{2})|\\(.)|([{}])|([^\\{}\r\n]+)|[\r\n]+", re.S)
_RTF_SKIP = {b"fonttbl", b"colortbl", b"stylesheet", b"info", b"pict", b"header", b"footer", b"headerl", b"headerr",
             b"headerf", b"footerl", b"footerr", b"footerf", b"footnote", b"annotation", b"object", b"themedata",
             b"colorschememapping", b"latentstyles", b"datastore", b"xmlnstbl", b"listtable", b"listoverridetable",
             b"rsidtbl", b"generator", b"fldinst", b"bkmkstart", b"bkmkend", b"filetbl", b"revtbl", b"pgdsctbl",
             b"mmathPr", b"wgrffmtfilter", b"shppict", b"nonshppict", b"blipuid"}
_RTF_CHARS = {b"par": "\n", b"line": "\n", b"sect": "\n", b"page": "\n", b"tab": "\t", b"cell": "\t", b"row": "\n",
              b"emdash": "—", b"endash": "–", b"lquote": "‘", b"rquote": "’", b"ldblquote": "“", b"rdblquote": "”",
              b"bullet": "•", b"emspace": " ", b"enspace": " ", b"qmspace": " "}


def rtf_text(data: bytes) -> str:
    if not data.lstrip().startswith(b"{\\rtf"):
        raise DocumentError("This is not an RTF document.")
    codepage = "cp1252"
    m = re.search(rb"\\ansicpg(\d+)", data[:2000])
    if m:
        codepage = f"cp{int(m.group(1))}"
        try:
            "".encode(codepage)
        except LookupError:
            codepage = "cp1252"
    out: list[str] = []
    pending = bytearray()           # \'hh bytes, decoded together (multi-byte code pages)
    stack: list[tuple[bool, int]] = []
    skipping, uc, skip_chars = False, 1, 0
    star = False

    def flush() -> None:
        if pending:
            if not skipping:
                out.append(pending.decode(codepage, "replace"))
            pending.clear()

    for t in _RTF_TOKEN.finditer(data):
        word, num, hexa, sym, brace, plain = t.groups()
        if hexa is not None:
            if skip_chars:
                skip_chars -= 1
                continue
            pending.append(int(hexa, 16))
            continue
        flush()
        if brace == b"{":
            stack.append((skipping, uc))
            star = False
        elif brace == b"}":
            if stack:
                skipping, uc = stack.pop()
            skip_chars = 0
        elif word is not None:
            if word in _RTF_SKIP or star:
                skipping = True
                star = False
            elif word == b"uc":
                uc = int(num or 1)
            elif word == b"u":
                if not skipping:
                    n = int(num or 0)
                    out.append(chr(n + 65536 if n < 0 else n))
                skip_chars = uc
            elif word in _RTF_CHARS and not skipping:
                out.append(_RTF_CHARS[word])
        elif sym is not None:
            if sym == b"*":
                star = True
            elif skipping:
                pass
            elif sym in (b"\\", b"{", b"}"):
                out.append(sym.decode())
            elif sym == b"~":
                out.append("\u00a0")
            elif sym == b"_":
                out.append("\u2011")
            elif sym in (b"\n", b"\r"):
                out.append("\n")
        elif plain is not None:
            if skip_chars:
                n = min(skip_chars, len(plain))
                plain = plain[n:]
                skip_chars -= n
            if plain and not skipping:
                out.append(plain.decode(codepage, "replace"))
    flush()
    return "".join(out)


# .doc (Word 97–2003)

def _bytes_io(data: bytes):
    import io
    return io.BytesIO(data)


class _CompoundFile:
    """A minimal reader of OLE2 compound files (MS-CFB): enough to read named streams."""

    FREE, END = 0xFFFFFFFF, 0xFFFFFFFE

    def __init__(self, data: bytes):
        if data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            raise DocumentError("This is not a Word 97–2003 document.")
        self.data = data
        self.sector_size = 1 << struct.unpack_from("<H", data, 0x1E)[0]
        self.mini_size = 1 << struct.unpack_from("<H", data, 0x20)[0]
        n_fat, first_dir = struct.unpack_from("<II", data, 0x2C)
        self.cutoff = struct.unpack_from("<I", data, 0x38)[0]
        first_minifat, n_minifat, first_difat, n_difat = struct.unpack_from("<IIII", data, 0x3C)
        difat = [x for x in struct.unpack_from("<109I", data, 0x4C)]
        sector, per = first_difat, self.sector_size // 4 - 1
        for _ in range(n_difat):
            if sector >= self.END - 1:
                break
            values = struct.unpack_from(f"<{per + 1}I", self._sector(sector))
            difat += values[:per]
            sector = values[per]
        self.fat: list[int] = []
        for s in difat[:n_fat]:
            if s < self.END - 1:
                self.fat += struct.unpack_from(f"<{self.sector_size // 4}I", self._sector(s))
        self.entries = []
        d = self._chain(first_dir)
        for off in range(0, len(d) - 127, 128):
            name_len = struct.unpack_from("<H", d, off + 0x40)[0]
            name = d[off:off + max(0, name_len - 2)].decode("utf-16-le", "replace")
            kind = d[off + 0x42]
            start, size = struct.unpack_from("<II", d, off + 0x74)
            self.entries.append((name, kind, start, size))
        root = self.entries[0]
        self.ministream = self._chain(root[2])[:root[3]]
        self.minifat = []
        if n_minifat:
            raw = self._chain(first_minifat)
            self.minifat = list(struct.unpack_from(f"<{len(raw) // 4}I", raw))

    def _sector(self, n: int) -> bytes:
        start = (n + 1) * self.sector_size
        return self.data[start:start + self.sector_size]

    def _chain(self, start: int) -> bytes:
        out, s, seen = [], start, set()
        while s < self.END - 1 and s not in seen and s < len(self.fat) + 1:
            seen.add(s)
            out.append(self._sector(s))
            s = self.fat[s] if s < len(self.fat) else self.END
        return b"".join(out)

    def _mini_chain(self, start: int) -> bytes:
        out, s, seen = [], start, set()
        while s < self.END - 1 and s not in seen and s < len(self.minifat):
            seen.add(s)
            out.append(self.ministream[s * self.mini_size:(s + 1) * self.mini_size])
            s = self.minifat[s]
        return b"".join(out)

    def stream(self, name: str) -> bytes | None:
        for entry_name, kind, start, size in self.entries:
            if kind == 2 and entry_name == name:
                raw = self._mini_chain(start) if size < self.cutoff else self._chain(start)
                return raw[:size]
        return None


def doc_text(data: bytes) -> str:
    cf = _CompoundFile(data)
    word = cf.stream("WordDocument")
    if word is None or struct.unpack_from("<H", word, 0)[0] != 0xA5EC:
        raise DocumentError("This is not a Word 97–2003 document.")
    flags = struct.unpack_from("<H", word, 0x0A)[0]
    if flags & 0x0100:
        raise DocumentError("This document is encrypted.")
    table = cf.stream("1Table" if flags & 0x0200 else "0Table")
    if table is None:
        raise DocumentError("The document's table stream is missing.")
    pos = 32
    csw = struct.unpack_from("<H", word, pos)[0]
    pos += 2 + csw * 2
    cslw = struct.unpack_from("<H", word, pos)[0]
    lw = struct.unpack_from(f"<{cslw}I", word, pos + 2)
    pos += 2 + cslw * 4
    ccp_text = lw[3]
    fc_clx, lcb_clx = struct.unpack_from("<II", word, pos + 2 + 33 * 8)
    clx = table[fc_clx:fc_clx + lcb_clx]
    i = 0
    while i < len(clx) and clx[i] == 1:  # skip the Prc entries
        i += 3 + struct.unpack_from("<H", clx, i + 1)[0]
    if i >= len(clx) or clx[i] != 2:
        raise DocumentError("The document's text could not be located.")
    lcb = struct.unpack_from("<I", clx, i + 1)[0]
    plc = clx[i + 5:i + 5 + lcb]
    n = (lcb - 4) // 12
    cps = struct.unpack_from(f"<{n + 1}I", plc, 0)
    pieces: list[str] = []
    for k in range(n):
        start, end = cps[k], min(cps[k + 1], ccp_text)
        if end <= start:
            continue
        fc_raw = struct.unpack_from("<I", plc, (n + 1) * 4 + k * 8 + 2)[0]
        count = end - start
        if fc_raw & 0x40000000:
            fc = (fc_raw & 0x3FFFFFFF) // 2
            pieces.append(word[fc:fc + count].decode("cp1252", "replace"))
        else:
            fc = fc_raw & 0x3FFFFFFF
            pieces.append(word[fc:fc + 2 * count].decode("utf-16-le", "replace"))
    return _word_controls("".join(pieces))


def _word_controls(text: str) -> str:
    """Word's control characters: paragraph and cell marks, and fields (keep the result, drop the code)."""
    out: list[str] = []
    depth_code: list[bool] = []   # per open field: still in its code part?
    for ch in text:
        if ch == "\x13":
            depth_code.append(True)
            continue
        if ch == "\x14":
            if depth_code:
                depth_code[-1] = False
            continue
        if ch == "\x15":
            if depth_code:
                depth_code.pop()
            continue
        if any(depth_code):
            continue
        if ch in "\r\x0b\x0c":
            out.append("\n")
        elif ch == "\x07":
            out.append("\t")
        elif ch == "\x1e":
            out.append("\u2011")
        elif ch == "\x1f" or (ord(ch) < 0x20 and ch not in "\t\n"):
            continue
        else:
            out.append(ch)
    return "".join(out)
