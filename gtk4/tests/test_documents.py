"""Tests of reading, writing and importing documents (qdvc/documents.py),
with the shared samples in ../sample-texts and a minimal Word 97 file built
here."""

import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT.parent / "sample-texts"
sys.path.insert(0, str(ROOT))

from qdvc import documents as D  # noqa: E402


def minimal_doc(compressed: str, unicode: str) -> bytes:
    """A Word 97 file with two text pieces: one compressed (cp1252), one UTF-16."""
    sector = 512
    word = bytearray(4096)
    struct.pack_into("<HH", word, 0, 0xA5EC, 0x00C1)
    struct.pack_into("<H", word, 0x0A, 0x0200)  # fWhichTblStm: 1Table
    pos = 32
    struct.pack_into("<H", word, pos, 14)
    pos += 2 + 28
    struct.pack_into("<H", word, pos, 22)
    lw = [0] * 22
    lw[3] = len(compressed) + len(unicode)  # ccpText
    struct.pack_into("<22I", word, pos + 2, *lw)
    pos += 2 + 88
    struct.pack_into("<H", word, pos, 93)
    rg = pos + 2
    text_a, text_b = 2048, 2560
    word[text_a:text_a + len(compressed)] = compressed.encode("cp1252")
    word[text_b:text_b + 2 * len(unicode)] = unicode.encode("utf-16-le")
    n1 = len(compressed)
    plc = struct.pack("<3I", 0, n1, n1 + len(unicode))
    plc += struct.pack("<HIH", 0, (text_a * 2) | 0x40000000, 0) + struct.pack("<HIH", 0, text_b, 0)
    table = bytearray(b"\x02" + struct.pack("<I", len(plc)) + plc)
    struct.pack_into("<II", word, rg + 33 * 8, 0, len(table))
    table += bytes(4096 - len(table))

    n_word, n_table = len(word) // sector, len(table) // sector
    fat = [0xFFFFFFFF] * (sector // 4)
    fat[0], fat[1] = 0xFFFFFFFD, 0xFFFFFFFE
    first_word, first_table = 2, 2 + n_word
    for i in range(n_word):
        fat[first_word + i] = first_word + i + 1 if i < n_word - 1 else 0xFFFFFFFE
    for i in range(n_table):
        fat[first_table + i] = first_table + i + 1 if i < n_table - 1 else 0xFFFFFFFE

    def entry(name, kind, start, size, child=0xFFFFFFFF, right=0xFFFFFFFF):
        raw = name.encode("utf-16-le") + b"\0\0"
        e = bytearray(128)
        e[:len(raw)] = raw
        struct.pack_into("<HBB", e, 0x40, len(raw), kind, 1)
        struct.pack_into("<III", e, 0x44, 0xFFFFFFFF, right, child)
        struct.pack_into("<II", e, 0x74, start, size)
        return bytes(e)

    directory = (entry("Root Entry", 5, 0xFFFFFFFE, 0, child=1) + entry("WordDocument", 2, first_word, len(word),
                 right=2) + entry("1Table", 2, first_table, len(table)) + bytes(128))
    header = bytearray(sector)
    header[:8] = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    struct.pack_into("<HHHHH", header, 0x18, 0x3E, 3, 0xFFFE, 9, 6)
    struct.pack_into("<IIIIIIIII", header, 0x2C, 1, 1, 0, 4096, 0xFFFFFFFE, 0, 0xFFFFFFFE, 0, 0)
    struct.pack_into("<109I", header, 0x4C, 0, *([0xFFFFFFFF] * 108))
    return bytes(header) + struct.pack(f"<{len(fat)}I", *fat) + directory + bytes(word) + bytes(table)


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="articulate-docs-"))

    def write(self, name, data: bytes) -> Path:
        p = self.tmp / name
        p.write_bytes(data)
        return p

    def test_decoding(self):
        self.assertEqual(D.decode("café".encode("utf-8")), "café")
        self.assertEqual(D.decode(b"\xef\xbb\xbfhi"), "hi")
        self.assertEqual(D.decode("hé".encode("utf-16")), "hé")
        self.assertEqual(D.decode("café".encode("cp1252")), "café")

    def test_line_endings_round_trip(self):
        p = self.write("crlf.txt", b"one\r\ntwo\r\n")
        text, ending = D.read_text_file(p)
        self.assertEqual((text, ending), ("one\ntwo\n", "\r\n"))
        D.write_text_file(p, text + "three\n", ending)
        self.assertEqual(p.read_bytes(), b"one\r\ntwo\r\nthree\r\n")

    def test_write_keeps_the_mode(self):
        p = self.write("mode.md", b"x")
        os.chmod(p, 0o640)
        D.write_text_file(p, "y")
        self.assertEqual(os.stat(p).st_mode & 0o777, 0o640)
        self.assertEqual(p.read_text(), "y")

    def test_shared_samples_import(self):
        expected = "Thank you all for joining us on monday."
        for name in ("sample.docx", "sample.odt", "sample.rtf"):
            text = D.import_document(SAMPLES / "imports" / name)
            self.assertIn(expected, text, name)
            self.assertIn("“", D.import_document(SAMPLES / "imports" / name) + "“")
            self.assertTrue(text.startswith("Quarterly update for the reading group\n"), name)
            self.assertIn("`teh_value = 1`", text, name)

    def test_docx_details(self):
        import zipfile
        import io
        w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
        xml = (f'<w:document {w}><w:body><w:p><w:r><w:t>Tab</w:t><w:tab/><w:t>here</w:t></w:r>'
               '<w:del><w:r><w:delText>gone</w:delText></w:r></w:del><w:r><w:br/><w:t>next</w:t></w:r></w:p>'
               '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>a</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>b</w:t></w:r>'
               '</w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("word/document.xml", xml)
        self.assertEqual(D.docx_text(buf.getvalue()), "Tab\there\nnext\na\n\tb\n\t")

    def test_odt_spaces_and_breaks(self):
        import zipfile
        import io
        t = 'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"'
        o = 'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"'
        xml = (f'<office:document-content {o} {t}><office:body><office:text><text:h>Title</text:h>'
               '<text:p>a<text:s text:c="3"/>b<text:tab/>c<text:line-break/>d <text:span>e</text:span>'
               '<text:note><text:note-body><text:p>note</text:p></text:note-body></text:note></text:p>'
               '</office:text></office:body></office:document-content>')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("content.xml", xml)
        self.assertEqual(D.odt_text(buf.getvalue()), "Title\na   b\tc\nd e\n")

    def test_rtf_details(self):
        rtf = (rb"{\rtf1\ansi\ansicpg1252{\fonttbl{\f0 Times;}}{\*\generator Test;}"
               rb"Caf\'e9 \u8212? done\par {\field{\*\fldinst HYPERLINK x}{\fldrslt link}}\tab end\line "
               rb"\{braces\}}")
        self.assertEqual(D.rtf_text(rtf), "Café — done\nlink\tend\n{braces}")

    def test_doc(self):
        p = self.write("old.doc", minimal_doc("Caf\xe9 one.\r\x13 HYPERLINK x \x14link\x15 two\r", "Ünïcode—fine\r"))
        self.assertEqual(D.import_document(p), "Café one.\nlink two\nÜnïcode—fine\n")

    def test_errors_are_for_people(self):
        with self.assertRaisesRegex(D.DocumentError, "can’t be imported"):
            D.import_document(self.write("page.html", b"<html></html>"))
        with self.assertRaisesRegex(D.DocumentError, "could not be read"):
            D.import_document(self.write("broken.docx", b"not a zip"))
        with self.assertRaisesRegex(D.DocumentError, "Word 97"):
            D.import_document(self.write("fake.doc", b"plain text"))


if __name__ == "__main__":
    unittest.main()
