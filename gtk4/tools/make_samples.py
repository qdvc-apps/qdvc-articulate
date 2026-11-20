#!/usr/bin/env python3
"""Write ../sample-texts/imports/: the shared sample (../sample-texts/sample.md)
as .docx, .odt and .rtf, for trying File › Import in either edition.

The files are small but complete enough for Word, LibreOffice and the
macOS text importers. (A .doc sample is not written: the binary Word
format cannot be produced faithfully without Word or LibreOffice. The
tests build a minimal one of their own for the .doc reader.)

    python3 tools/make_samples.py
"""

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT.parent / "sample-texts"


def paragraphs() -> list[str]:
    text = (SAMPLES / "sample.md").read_text(encoding="utf-8")
    out = []
    for block in text.split("\n\n"):
        block = block.strip().lstrip("# ").replace("\n", " ")
        if block:
            out.append(block)
    return out


def write_docx(path: Path, paras: list[str]) -> None:
    body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{escape(p)}</w:t></w:r></w:p>' for p in paras)
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                f'<w:body>{body}<w:sectPr/></w:body></w:document>')
    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="xml" ContentType="application/xml"/>'
                     '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
                     'officedocument.wordprocessingml.document.main+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'officeDocument" Target="word/document.xml"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)


def write_odt(path: Path, paras: list[str]) -> None:
    body = "".join(f"<text:p>{escape(p)}</text:p>" for p in paras)
    content = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
               'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.3">'
               f'<office:body><office:text>{body}</office:text></office:body></office:document-content>')
    manifest = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
                'manifest:version="1.3">'
                '<manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.'
                'opendocument.text"/>'
                '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
                '</manifest:manifest>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/manifest.xml", manifest)
        z.writestr("content.xml", content)


def rtf_escape(text: str) -> str:
    out = []
    for ch in text:
        if ch in "\\{}":
            out.append("\\" + ch)
        elif ord(ch) > 127:
            out.append(f"\\u{ord(ch) if ord(ch) < 32768 else ord(ch) - 65536}?")
        else:
            out.append(ch)
    return "".join(out)


def write_rtf(path: Path, paras: list[str]) -> None:
    body = "\\par\n".join(rtf_escape(p) for p in paras)
    path.write_text("{\\rtf1\\ansi\\ansicpg1252\\deff0{\\fonttbl{\\f0 Helvetica;}}\\f0\\fs24\n" + body + "\\par\n}\n",
                    encoding="ascii")


def main() -> None:
    out = SAMPLES / "imports"
    out.mkdir(parents=True, exist_ok=True)
    paras = paragraphs()
    write_docx(out / "sample.docx", paras)
    write_odt(out / "sample.odt", paras)
    write_rtf(out / "sample.rtf", paras)
    print(f"Wrote {out}/sample.docx, sample.odt, sample.rtf")


if __name__ == "__main__":
    main()
