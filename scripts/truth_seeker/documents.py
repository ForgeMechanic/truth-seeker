"""Offline extraction and deterministic locators. Never follows embedded references."""
import ast
import io
import re
import platform
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

from .errors import MissingEvidence
from .util import digest

EXTRACTOR = "truth-seeker-text-v1"


class HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0
        self.headings = []
        self.heading = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if tag in ("p", "div", "br", "li", "tr") or re.fullmatch(r"h[1-6]", tag):
            self.parts.append("\n")
        if re.fullmatch(r"h[1-6]", tag):
            self.heading = [int(tag[1]), dict(attrs).get("id"), len(self.parts), []]

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        if re.fullmatch(r"h[1-6]", tag) and self.heading:
            level, anchor, start, parts = self.heading
            self.headings.append((level, anchor, start, "".join(parts).strip()))
            self.heading = None
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)
            if self.heading:
                self.heading[3].append(data)


def markdown_sections(text):
    headings = []
    stack = []
    offset = 0
    fence = None
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        marker = re.match(r"(`{3,}|~{3,})", stripped)
        if marker:
            char = marker[1][0]
            if fence is None:
                fence = char
            elif fence == char:
                fence = None
        if fence is None:
            match = re.match(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", line.rstrip("\r\n"))
            if match:
                level, title = len(match[1]), re.sub(r"[ \t]+#+[ \t]*$", "", match[2])
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, title))
                headings.append((level, [item[1] for item in stack], offset))
        offset += len(line)
    return headings


def choose_section(text, headings, matches):
    if len(matches) != 1:
        raise MissingEvidence(f"Section selector matched {len(matches)} sections; clarify locator")
    index = matches[0]
    level, _, start = headings[index]
    end = next((entry[2] for entry in headings[index + 1:] if entry[0] <= level), len(text))
    return text[start:end]


def extract(data, kind, selector=None):
    selector = selector or {}
    if not isinstance(selector, dict) or len(selector) > 1:
        raise MissingEvidence("Use exactly one selector, or an empty object for the whole document")
    parser_id = "stdlib-python-" + platform.python_version()
    try:
        if kind == "pdf":
            from pypdf import PdfReader, __version__ as pdf_version
            parser_id = "pypdf-" + pdf_version
            reader = PdfReader(io.BytesIO(data))
            pages = [page.extract_text() or "" for page in reader.pages]
            if "pages" in selector:
                first, last = selector["pages"]
                if first < 1 or last < first or last > len(pages):
                    raise MissingEvidence("PDF page range not found")
                text = "\n".join(pages[first - 1:last])
            elif "bookmark" in selector:
                found = []
                def walk(items, depth=0):
                    for item in items:
                        if isinstance(item, list):
                            walk(item, depth + 1)
                        else:
                            found.append((item, depth))
                walk(reader.outline)
                matches = [i for i, (item, _) in enumerate(found) if item.title == selector["bookmark"]]
                if len(matches) != 1:
                    raise MissingEvidence("PDF bookmark missing or ambiguous")
                i = matches[0]
                first = reader.get_destination_page_number(found[i][0])
                following = next((item for item, depth in found[i + 1:] if depth <= found[i][1]), None)
                last = reader.get_destination_page_number(following) if following is not None else len(pages)
                if first is None or last is None or last <= first:
                    raise MissingEvidence("PDF bookmark boundaries ambiguous; supply pages")
                text = "\n".join(pages[first:last])
            elif selector:
                raise MissingEvidence("PDF supports pages or bookmark selectors")
            else:
                text = "\n".join(pages)
            if not text.strip():
                raise MissingEvidence("PDF has no extractable text; supply an approved text/OCR artifact")
        elif kind == "docx":
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                info = archive.getinfo("word/document.xml")
                if info.file_size > 32 * 1024 * 1024:
                    raise MissingEvidence("Word XML exceeds extraction limit")
                root = ET.fromstring(archive.read(info))
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            parts, headings = [], []
            position = 0
            for paragraph in root.findall(".//w:p", ns):
                content = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)) + "\n"
                style = paragraph.find("w:pPr/w:pStyle", ns)
                if style is not None:
                    value = style.get(f"{{{ns['w']}}}val", "")
                    match = re.fullmatch(r"Heading([1-9])", value, re.I)
                    if match:
                        headings.append((int(match[1]), content.strip(), position))
                parts.append(content)
                position += len(content)
            text = "".join(parts)
            if "heading" in selector:
                text = choose_section(text, headings, [i for i, h in enumerate(headings) if h[1] == selector["heading"]])
            elif selector:
                raise MissingEvidence("Word supports a heading selector")
        elif kind == "html":
            parser = HTMLText()
            parser.feed(data.decode("utf-8-sig"))
            text = "".join(parser.parts)
            headings = [(h[0], h[3], len("".join(parser.parts[:h[2]]))) for h in parser.headings]
            if selector:
                key = "anchor" if "anchor" in selector else "heading"
                if key not in selector:
                    raise MissingEvidence("HTML supports heading or heading-anchor selectors")
                matches = [i for i, h in enumerate(parser.headings)
                           if (h[1] if key == "anchor" else h[3]) == selector[key]]
                text = choose_section(text, headings, matches)
        else:
            text = data.decode("utf-8-sig")
            if kind == "markdown" and selector:
                headings = markdown_sections(text)
                if "heading_path" in selector:
                    matches = [i for i, h in enumerate(headings) if h[1] == selector["heading_path"]]
                elif "heading" in selector:
                    matches = [i for i, h in enumerate(headings) if h[1][-1] == selector["heading"]]
                else:
                    raise MissingEvidence("Markdown supports heading or heading_path selectors")
                text = choose_section(text, headings, matches)
            elif "python" in selector:
                tree = ast.parse(text)
                found = []
                def visit(nodes, prefix=""):
                    for node in nodes:
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            name = prefix + node.name
                            if name == selector["python"]:
                                found.append(node)
                            visit(node.body, name + ".")
                visit(tree.body)
                if len(found) != 1:
                    raise MissingEvidence("Python symbol missing or ambiguous")
                node = found[0]
                start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
                text = "".join(text.splitlines(keepends=True)[start - 1:node.end_lineno])
            elif "lines" in selector:
                first, last = selector["lines"]
                lines = text.splitlines(keepends=True)
                if first < 1 or last < first or last > len(lines):
                    raise MissingEvidence("Line range not found")
                text = "".join(lines[first - 1:last])
            elif selector:
                raise MissingEvidence("Unsupported selector for text artifact")
    except MissingEvidence:
        raise
    except Exception as exc:
        raise MissingEvidence(f"Cannot extract {kind}: {exc}") from exc
    return {"text": text, "content_hash": digest(text.encode()), "artifact_hash": digest(data),
            "extractor": EXTRACTOR, "parser": parser_id, "selector": selector}


def infer_kind(path):
    return {".md": "markdown", ".pdf": "pdf", ".html": "html", ".htm": "html", ".docx": "docx"}.get(Path(path).suffix.lower(), "text")
