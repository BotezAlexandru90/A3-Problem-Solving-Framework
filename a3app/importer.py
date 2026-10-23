"""Turn notes / emails / documents into *candidate* A3 content.

This is keyword-based pre-sorting, not AI. Every imported sentence is marked
[UNVERIFIED IMPORT] and counts as empty for the quality gates until a person
reviews and edits it.
"""
import html
import re
import zipfile
from io import BytesIO

MARK = "[UNVERIFIED IMPORT]"
MAX_SENTENCES = 200
MAX_XML_BYTES = 20 * 1024 * 1024  # guards against zip bombs

TARGETS = [
    ("skip", "Skip"),
    ("background", "Step A - History and background"),
    ("symptom", "Step A - Symptom"),
    ("problem_statement", "Step A - Problem description"),
    ("expected_condition", "Step A - Expected requirement"),
    ("data_sources", "Step A - Data sources"),
    ("containment", "Step A - Containment action (new action)"),
    ("hypothesis", "Step B - Cause hypothesis (new, Untested)"),
]
TARGET_KEYS = {k for k, _ in TARGETS}

RULES = [
    ("hypothesis", re.compile(r"\b(because|due to|caused by|root cause|suspect\w*|probabl\w+|likely|might|may be|"
                              r"assum\w+|hypothes\w+)\b", re.I)),
    ("containment", re.compile(r"\b(contain\w*|sort(ed|ing)?|quarantin\w+|block(ed)?|100\s?% inspection|"
                               r"stop ship|on hold|segregat\w+)\b", re.I)),
    ("data_sources", re.compile(r"\b(CQTS|SAP|CBW|WISE|AMT|AOD|vLIB|report|according to|data from|database|"
                                r"measurement|log file)\b", re.I)),
    ("expected_condition", re.compile(r"\b(spec(ification)?|requirement|tolerance|drawing|standard|shall)\b", re.I)),
    ("problem_statement", re.compile(r"\d+(\.\d+)?\s?(ppm|%|pcs|parts|units|defects?|complaints?|rejects?|"
                                     r"failures?|returns?)\b", re.I)),
    ("symptom", re.compile(r"\b(observed|noise|crack\w*|leak\w*|broken|error|fault|fail\w*|not working|"
                           r"deviation|damage\w*)\b", re.I)),
]


def _docx_like_text(data, member_pattern, text_tag):
    out = []
    total = 0
    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = sorted(n for n in zf.namelist() if re.fullmatch(member_pattern, n))
        for name in names:
            info = zf.getinfo(name)
            total += info.file_size
            if total > MAX_XML_BYTES:
                raise ValueError("Document is too large to import.")
            xml = zf.read(name).decode("utf-8", "ignore")
            # paragraphs -> newlines, then pull text runs
            xml = re.sub(r"</(w|a):p>", "\n", xml)
            runs = re.findall(rf"<{text_tag}(?:\s[^>]*)?>([^<]*)</{text_tag}>|(\n)", xml)
            out.append("".join(t or nl for t, nl in runs))
    return html.unescape("\n".join(out))


def extract_text(filename, data):
    name = (filename or "").lower()
    if name.endswith(".docx"):
        return _docx_like_text(data, r"word/document\.xml", "w:t")
    if name.endswith(".pptx"):
        return _docx_like_text(data, r"ppt/slides/slide\d+\.xml", "a:t")
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages[:100])
    if name.endswith((".txt", ".md", ".eml", ".csv")):
        return data.decode("utf-8", "ignore")
    raise ValueError("Supported files: .docx, .pptx, .pdf, .txt, .md, .eml, .csv")


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    out = []
    for p in parts:
        p = " ".join(p.split())
        if len(p) >= 15:
            out.append(p[:1000])
    return out[:MAX_SENTENCES]


def classify(sentence):
    for target, rx in RULES:
        if rx.search(sentence):
            return target
    return "background"
