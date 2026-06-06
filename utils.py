# -*- coding: utf-8 -*-
"""
utils.py — shared helpers for the Adobe PDF extraction pipeline.
"""
import unicodedata


def get_element_type(path: str) -> str:
    """Map an Adobe PDF element Path string to a normalised element type.

    Check order matters: more specific tags come before substrings they contain,
    and ALL table-related tags come before "p" so that paths like
    //Document/Table/TR/TD/P are classified as "table_cell", not "paragraph".
    """
    p = path.lower()

    if "title" in p:
        return "title"
    if "figure" in p:
        return "figure"
    if "footnote" in p:
        return "footnote"
    if "aside" in p:
        return "aside"
    if any(h in p for h in ["h1", "h2", "h3", "h4", "h5", "h6", "/h[", "/h "]):
        return "heading"
    # Span variants before bare "p"
    if "paragraphspan" in p:
        return "paragraph_span"
    if "stylespan" in p:
        return "style_span"
    if "subparagraph" in p or "/sub" in p:
        return "subparagraph"
    # List elements
    if "lbody" in p:
        return "list_item_body"
    if "lbl" in p:
        return "list_item_label"
    if "li" in p:
        return "list_item"
    if "/l" in p:
        return "list"
    # Table elements — all checked BEFORE "p" to prevent //Table/TR/TD/P → paragraph
    if "toci" in p:
        return "table_of_contents_item"
    if "toc" in p:
        return "table_of_contents"
    if "th" in p:
        return "table_header_cell"
    if "td" in p:
        return "table_cell"
    if "tr" in p:
        return "table_row"
    if "table" in p:
        return "table"
    # Plain paragraph — only reached when no table tag is present in the path
    if "p" in p:
        return "paragraph"
    if "reference" in p:
        return "reference"
    if "sect" in p:
        return "section"
    if "watermark" in p:
        return "watermark"
    return "other"


def clean_text(text: str) -> str:
    """Replace tabs and fix common corrupted / curly Unicode characters."""
    text = text.replace('\t', ' ')
    replacements = {
        '�': '',       # replacement character
        '→': '->',     # →
        '–': '-',      # –
        '—': '--',     # —
        '‘': "'",      # '
        '’': "'",      # '
        '“': '"',      # "
        '”': '"',      # "
        '•': '*',      # •
        '…': '...',    # …
        ' ': ' ',      # non-breaking space
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    cleaned = []
    for char in text:
        if char in '\n\r\t ':
            cleaned.append(char)
        elif ord(char) < 128 or unicodedata.category(char)[0] not in ('C', 'Z'):
            cleaned.append(char)
        else:
            cleaned.append(' ')
    return ''.join(cleaned)
