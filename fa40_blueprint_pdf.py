"""
Freedom After 40 - Blueprint PDF Generator v2
Parses real markdown from Lovable's blueprint-stream outputs.

Three PDF types:
  income    - Income Freedom Builder (from income assessment)
  blueprint - Freedom Blueprint (free tier)
  enhanced  - Enhanced Blueprint (paid tier)

Entry point:
  from fa40_blueprint_pdf import generate_pdf
  path = generate_pdf(data)
  # data = webhook payload with 'type', 'blueprintMarkdown', 'email',
  #        'stripe_first_name', 'stripe_last_name', 'sessionId'
"""

import re, os

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak, Flowable, NextPageTemplate
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Brand Colors ──────────────────────────────────────────────────────────────
PLUM        = colors.HexColor("#3D1F3D")
GOLD        = colors.HexColor("#C9A84C")
GOLD_LIGHT  = colors.HexColor("#E8D5A3")
CREAM       = colors.HexColor("#FAF7F2")
CREAM_DARK  = colors.HexColor("#F0EBE3")
BODY_TEXT   = colors.HexColor("#4A3840")
MUTED       = colors.HexColor("#8B7580")
WHITE       = colors.white
CARD_BORDER = colors.HexColor("#E0D5D8")
PLUM_BORDER = colors.HexColor("#D4BED4")

# ── Fonts ─────────────────────────────────────────────────────────────────────
_local_fonts = os.path.join(_SCRIPT_DIR, "fonts")
FONT_DIR = (
    os.environ.get("FONT_DIR")
    or (_local_fonts if os.path.isdir(_local_fonts) else "/usr/share/fonts/truetype/google-fonts")
)

# ── Assets ────────────────────────────────────────────────────────────────────
DOVE_PATH = os.environ.get("DOVE_PATH") or os.path.join(_SCRIPT_DIR, "dove_transparent.png")

_FONT_MAP = {
    "Lora":           f"{FONT_DIR}/Lora-Variable.ttf",
    "Lora-Italic":    f"{FONT_DIR}/Lora-Italic-Variable.ttf",
    "Poppins":        f"{FONT_DIR}/Poppins-Regular.ttf",
    "Poppins-Light":  f"{FONT_DIR}/Poppins-Light.ttf",
    "Poppins-Medium": f"{FONT_DIR}/Poppins-Medium.ttf",
    "Poppins-Bold":   f"{FONT_DIR}/Poppins-Bold.ttf",
}
# Fallback to built-in ReportLab fonts when custom fonts are absent
_FALLBACKS = {
    "Lora":           "Times-Roman",
    "Lora-Italic":    "Times-Italic",
    "Poppins":        "Helvetica",
    "Poppins-Light":  "Helvetica",
    "Poppins-Medium": "Helvetica-Bold",
    "Poppins-Bold":   "Helvetica-Bold",
}

def register_fonts():
    """Register custom fonts; returns set of names that failed to load."""
    failed = set()
    for name, path in _FONT_MAP.items():
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                continue
            except Exception as exc:
                print(f"Warning: could not load font '{name}': {exc}")
        failed.add(name)
    return failed

_missing_fonts = register_fonts()

def _apply_font_fallbacks(styles_dict):
    """Patch ParagraphStyle objects to use built-in fonts when custom ones are missing."""
    if not _missing_fonts:
        return
    for style in styles_dict.values():
        fn = style.fontName
        if fn in _missing_fonts:
            style.fontName = _FALLBACKS.get(fn, "Helvetica")

# Styles are built after this point and patched after S is defined

# ── Styles ────────────────────────────────────────────────────────────────────
S = {
    "cover_eyebrow":   ParagraphStyle("ce",  fontName="Poppins-Medium", fontSize=9,  textColor=GOLD,       spaceAfter=6,  tracking=3),
    "cover_title":     ParagraphStyle("ct",  fontName="Lora",           fontSize=30, textColor=WHITE,      leading=36,    spaceAfter=4),
    "cover_title_i":   ParagraphStyle("cti", fontName="Lora-Italic",    fontSize=30, textColor=GOLD_LIGHT, leading=36,    spaceAfter=8),
    "cover_subtitle":  ParagraphStyle("cs",  fontName="Poppins-Light",  fontSize=11, textColor=GOLD,       spaceAfter=24, tracking=2),
    "cover_for":       ParagraphStyle("cf",  fontName="Poppins-Medium", fontSize=9,  textColor=GOLD,       spaceAfter=3,  tracking=2),
    "cover_recipient": ParagraphStyle("cr",  fontName="Lora-Italic",    fontSize=18, textColor=WHITE),
    "cover_date":      ParagraphStyle("cd",  fontName="Poppins-Light",  fontSize=9,  textColor=colors.HexColor("#8B7A8B"), alignment=TA_RIGHT),
    "section_label":   ParagraphStyle("sl",  fontName="Poppins-Medium", fontSize=9,  textColor=GOLD,       spaceBefore=4, spaceAfter=6, tracking=3),
    "section_heading": ParagraphStyle("sh",  fontName="Lora",           fontSize=22, textColor=PLUM,       spaceAfter=12, leading=28),
    "section_heading_lg": ParagraphStyle("shl", fontName="Lora",        fontSize=18, textColor=PLUM,       spaceAfter=10, leading=24, spaceBefore=4),
    "viability_def":   ParagraphStyle("vd",  fontName="Poppins-Light",  fontSize=10, textColor=MUTED,      leading=15,    fontStyle="italic", spaceAfter=4),
    "market_energy":   ParagraphStyle("me",  fontName="Poppins-Light",  fontSize=11, textColor=PLUM,       leading=18,    spaceAfter=8),
    "intro_text":      ParagraphStyle("it",  fontName="Poppins-Light",  fontSize=11, textColor=BODY_TEXT,  leading=18,    spaceAfter=8),
    "narrative":       ParagraphStyle("nar", fontName="Poppins-Light",  fontSize=11, textColor=BODY_TEXT,  leading=18,    spaceAfter=8),
    "concept_title":   ParagraphStyle("cot", fontName="Lora",           fontSize=16, textColor=PLUM,       spaceAfter=2,  leading=20),
    "concept_meta":    ParagraphStyle("com", fontName="Poppins-Medium", fontSize=9,  textColor=GOLD,       tracking=1),
    "sub_label":       ParagraphStyle("subl",fontName="Poppins-Medium", fontSize=9,  textColor=GOLD,       spaceAfter=3,  tracking=2),
    "sub_text":        ParagraphStyle("subt",fontName="Poppins-Light",  fontSize=11, textColor=BODY_TEXT,  leading=17),
    "action_bold":     ParagraphStyle("ab",  fontName="Poppins-Medium", fontSize=11, textColor=PLUM,       spaceAfter=3,  leading=16),
    "action_body":     ParagraphStyle("abo", fontName="Poppins-Light",  fontSize=11, textColor=BODY_TEXT,  leading=17,    spaceAfter=10),
    "synthesis_label": ParagraphStyle("yl",  fontName="Poppins-Medium", fontSize=9,  textColor=GOLD,       spaceAfter=4,  tracking=2),
    "synthesis_quote": ParagraphStyle("yq",  fontName="Lora-Italic",    fontSize=13, textColor=WHITE,      leading=20,    spaceAfter=8),
    "synthesis_text":  ParagraphStyle("yt",  fontName="Poppins-Light",  fontSize=11, textColor=colors.HexColor("#D4C4C8"), leading=17),
    "strength_label":  ParagraphStyle("stl", fontName="Poppins-Medium", fontSize=9,  textColor=GOLD,       spaceAfter=2,  tracking=2),
    "strength_title":  ParagraphStyle("stt", fontName="Lora",           fontSize=14, textColor=PLUM,       spaceAfter=4,  leading=18),
    "strength_text":   ParagraphStyle("stx", fontName="Poppins-Light",  fontSize=11, textColor=BODY_TEXT,  leading=17),
    "ai_label":        ParagraphStyle("ail", fontName="Poppins-Medium", fontSize=9,  textColor=MUTED,      spaceAfter=2,  tracking=2),
    "ai_text":         ParagraphStyle("ait", fontName="Poppins-Light",  fontSize=11, textColor=MUTED,      leading=16,    fontStyle="italic"),
    "blocking_title":  ParagraphStyle("blt", fontName="Lora",           fontSize=13, textColor=PLUM,       spaceAfter=4,  leading=17),
    "blocking_text":   ParagraphStyle("blx", fontName="Poppins-Light",  fontSize=11, textColor=BODY_TEXT,  leading=17),
    "next_step_bold":  ParagraphStyle("nsb", fontName="Poppins-Medium", fontSize=11, textColor=PLUM,       spaceAfter=2,  leading=16),
    "next_step_text":  ParagraphStyle("nst", fontName="Poppins-Light",  fontSize=11, textColor=BODY_TEXT,  leading=17,    spaceAfter=10),
    "cta_text":        ParagraphStyle("ctat",fontName="Poppins-Light",  fontSize=11, textColor=BODY_TEXT,  alignment=TA_CENTER, leading=16),
    "cta_url":         ParagraphStyle("ctau",fontName="Poppins-Medium", fontSize=11, textColor=PLUM,       alignment=TA_CENTER),
    "footer_text":     ParagraphStyle("ft",  fontName="Poppins-Light",  fontSize=9,  textColor=MUTED,      alignment=TA_CENTER, tracking=1),
    "ib_score":        ParagraphStyle("ibs", fontName="Lora",           fontSize=42, textColor=PLUM,       leading=46),
    "ib_price":        ParagraphStyle("ibp", fontName="Lora",           fontSize=22, textColor=PLUM,       leading=28,    spaceAfter=4),
    "ib_buyer":        ParagraphStyle("ibb", fontName="Lora-Italic",    fontSize=12, textColor=BODY_TEXT,  leading=19),
}
_apply_font_fallbacks(S)

def _font(name):
    """Resolve a font name to its fallback if the custom font wasn't loaded."""
    return _FALLBACKS.get(name, name) if name in _missing_fonts else name

# ── Primitives ────────────────────────────────────────────────────────────────
def sp(h=0.15): return Spacer(1, h * inch)
def hr(color=CARD_BORDER, t=0.5, b=0, a=6): return HRFlowable(width="100%", thickness=t, color=color, spaceBefore=b, spaceAfter=a)

def plain_text(md_text):
    """Strip markdown bold/italic markers and links for clean PDF text."""
    t = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', md_text)
    t = re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
    t = re.sub(r'\*([^*]+)\*', r'\1', t)
    t = t.replace('[DISCOVERY_CALL_BUTTON]', '').strip()
    return t

# ── Cover Page ────────────────────────────────────────────────────────────────
COVER_CONFIG = {
    "enhanced":  ("YOUR FREEDOM BLUEPRINT",    "This is what we found.",  "Built around you.",                "Income concepts \u2022 Strengths \u2022 Strategic path"),
    "blueprint": ("YOUR FREEDOM BLUEPRINT",    "Your skills have",        "market value.",                    "Income concepts \u2022 Strengths \u2022 Strategic path"),
    "income":    ("YOUR INCOME FREEDOM BUILDER","Your Income",            "Concepts.",                        "Your idea \u2022 Viability \u2022 Pricing \u2022 Audience"),
}

def cover_identifier(data):
    t = data.get("type","blueprint")
    if t == "enhanced":
        name = data.get("name") or f"{data.get('stripe_first_name','')} {data.get('stripe_last_name','')}".strip()
        return ("PREPARED FOR", name) if name else (None, None)
    elif t == "blueprint":
        email = data.get("email","")
        return ("PREPARED FOR", email) if email else (None, None)
    return (None, None)

class FullBleedCover(Flowable):
    """
    Printer-friendly cover: deep plum header band top third,
    clean cream lower two thirds with logo wordmark and details.
    """
    def __init__(self, data):
        Flowable.__init__(self)
        self.data = data
        self.width, self.height = letter

    def draw(self):
        c = self.canv
        W, H = self.width, self.height
        t = self.data.get("type","blueprint")
        eyebrow, line1, line2, subtitle = COVER_CONFIG.get(t, COVER_CONFIG["blueprint"])

        pad_l = 0.75 * inch
        pad_r = W - 0.75 * inch

        # ── Cream background (full page) ──
        c.setFillColor(CREAM)
        c.rect(0, 0, W, H, fill=1, stroke=0)

        # ── Deep plum header band (top 42% of page) ──
        band_h = H * 0.42
        c.setFillColor(PLUM)
        c.rect(0, H - band_h, W, band_h, fill=1, stroke=0)

        # ── Gold accent bar at bottom of plum band ──
        c.setFillColor(GOLD)
        c.rect(0, H - band_h - 4, W, 4, fill=1, stroke=0)

        # Override subtitle for contribution-path users
        contribution_intents = (
            "Maybe someday, but it's not my focus right now",
            "No — my contribution isn't about income",
        )
        if t == "enhanced" and self.data.get("businessIntent") in contribution_intents:
            subtitle = "Contribution pathways • Strengths • Strategic path"

        # ── Text in plum band ──
        y = H - 0.65 * inch

        # FA40 wordmark
        c.setFont(_font("Poppins-Medium"), 9)
        c.setFillColor(GOLD)
        c.drawString(pad_l, y, "FREEDOM AFTER 40")
        y -= 0.5 * inch

        # Eyebrow
        c.setFont(_font("Poppins-Medium"), 9)
        c.setFillColor(colors.HexColor("#C9A84C"))
        c.drawString(pad_l, y, eyebrow)
        y -= 0.55 * inch

        # Title line 1
        c.setFont(_font("Lora"), 32)
        c.setFillColor(WHITE)
        c.drawString(pad_l, y, line1)
        y -= 0.55 * inch

        # Title line 2 italic
        c.setFont(_font("Lora-Italic"), 32)
        c.setFillColor(GOLD_LIGHT)
        c.drawString(pad_l, y, line2)
        y -= 0.5 * inch

        # Subtitle
        c.setFont(_font("Poppins-Light"), 11)
        c.setFillColor(GOLD)
        c.drawString(pad_l, y, subtitle)

        # ── Lower cream section ──
        # Gold dove logo - centered horizontally, pushed well down
        dove_path = DOVE_PATH
        dove_w = 2.4 * inch
        dove_h = 2.01 * inch  # maintain 715:598 ratio
        dove_x = (W - dove_w) / 2  # centered
        dove_y = H - band_h - 1.6 * inch - dove_h
        c.drawImage(dove_path, dove_x, dove_y,
                    width=dove_w, height=dove_h, mask='auto')

        # Thin gold rule well below dove
        rule_y = dove_y - 0.55 * inch
        c.setStrokeColor(GOLD)
        c.setLineWidth(0.75)
        c.line(pad_l, rule_y, pad_r, rule_y)

        # Identifier block
        id_label, id_value = cover_identifier(self.data)
        det_y = rule_y - 0.45 * inch
        if id_label and id_value:
            c.setFont(_font("Poppins-Medium"), 9)
            c.setFillColor(GOLD)
            c.drawString(pad_l, det_y, id_label)
            det_y -= 0.32 * inch
            c.setFont(_font("Lora-Italic"), 18)
            c.setFillColor(PLUM)
            c.drawString(pad_l, det_y, id_value)
            det_y -= 0.38 * inch
        else:
            det_y -= 0.1 * inch

        # Date line
        c.setFont(_font("Poppins-Light"), 9)
        c.setFillColor(MUTED)
        c.drawString(pad_l, det_y, "May 2026  \u2022  freedomafter40.com")

        # Footer rule
        c.setStrokeColor(colors.HexColor("#E0D5D8"))
        c.setLineWidth(0.5)
        c.line(pad_l, 0.6*inch, pad_r, 0.6*inch)

        # Footer text
        c.setFont(_font("Poppins-Light"), 8)
        c.setFillColor(MUTED)
        c.drawCentredString(W/2, 0.4*inch,
            "Freedom After 40  \u2022  freedomafter40.com  \u2022  hello@freedomafter40.com")

    def wrap(self, availWidth, availHeight):
        return self.width, self.height


def cover_page(data):
    return [FullBleedCover(data), NextPageTemplate('Later'), PageBreak()]

# ── Shared Closing ────────────────────────────────────────────────────────────
def closing_block():
    closing_lines = [
        "You showed up for yourself today. That matters more than you know.",
        "Everything in this Blueprint was built from what you shared, and it reflects something true: "
        "what you carry is real, it is valuable, and the world needs what only you can give.",
        "Sit with that. Read this more than once. Let the ideas breathe.",
        "There is no timeline here. Just a woman who is more ready than she realizes.",
    ]

    elements = [
        sp(0.25),
        HRFlowable(width="100%", thickness=0.75, color=GOLD, spaceBefore=0, spaceAfter=14),
    ]
    for line in closing_lines:
        elements.append(Paragraph(line, S["narrative"]))
        elements.append(sp(0.05))

    elements.append(sp(0.15))
    elements.append(Paragraph("I'm already rooting for you.", S["narrative"]))
    elements.append(sp(0.08))
    elements.append(Paragraph("With belief in what's coming,", S["narrative"]))
    elements.append(sp(0.12))
    elements.append(Paragraph("Cynthia", S["section_heading"]))
    elements.append(sp(0.25))

    cta_rows = [
        [Paragraph("When you are ready to build this, we are ready to help.", S["cta_text"])],
        [sp(0.08)],
        [Paragraph("freedomafter40.com  \u2022  hello@freedomafter40.com", S["cta_url"])],
    ]
    tbl = Table(cta_rows, colWidths=[6.6*inch])
    tbl.setStyle(TableStyle([
        ("ALIGN",        (0,0),(-1,-1),"CENTER"),
        ("LEFTPADDING",  (0,0),(-1,-1), 20),
        ("RIGHTPADDING", (0,0),(-1,-1), 20),
        ("TOPPADDING",   (0,0),(0,0),   20),
        ("BOTTOMPADDING",(0,-1),(-1,-1),20),
        ("TOPPADDING",   (0,1),(-1,-1), 0),
        ("BOTTOMPADDING",(0,0),(-1,-2), 0),
        ("LINEABOVE",    (0,0),(-1,0),  1.5, GOLD),
    ]))
    elements.append(tbl)
    return elements

# ── Markdown Parser ───────────────────────────────────────────────────────────

def parse_enhanced_blueprint(md):
    """
    Parse real Enhanced Blueprint markdown into structured dict.
    Handles ### headers and **Label:** blocks.
    The markdown uses ### for all section and concept headings.
    Known sections are detected by keyword; unknown ### lines are concept titles.
    """
    lines = md.split('\n')
    result = {
        "intro_paragraphs": [],
        "concepts": [],
        "contribution_pathways": [],
        "synthesis": {"mirror": "", "map": []},
        "emotional_strengths": [],
        "spiritual_strengths": [],
        "creative_strengths": [],
        "blocking_patterns": [],
        "next_steps": [],
        "next_steps_intro": "",
        "next_steps_closing": "",
    }

    def norm(s): return re.sub(r'[#*\s]+', ' ', s).strip().upper()

    # Keywords that identify known section headers (not concept titles)
    KNOWN_SECTIONS = [
        "THE MIRROR", "THE MAP", "YOUR EMOTIONAL STRENGTHS",
        "YOUR SPIRITUAL STRENGTHS", "YOUR CREATIVE STRENGTHS",
        "WHAT IS QUIETLY BLOCKING YOU", "NEXT STEPS",
        "YOUR SYNTHESIS", "YOUR INCOME CONCEPTS", "YOUR CONTRIBUTION PATHWAYS",
    ]

    def is_known_section(n):
        return any(kw in n for kw in KNOWN_SECTIONS)

    i = 0
    current_section = "intro"
    current_concept = None
    current_strength_section = None
    in_mirror = False
    in_map = False

    def flush_concept():
        if current_concept and current_concept.get("title"):
            if "_strength_body_lines" in current_concept and current_strength_section is not None:
                body = " ".join(current_concept["_strength_body_lines"])
                current_strength_section.append({"title": current_concept["title"], "body": body})
            elif current_section == "contribution_pathways":
                result["contribution_pathways"].append(current_concept)
            else:
                result["concepts"].append(current_concept)

    while i < len(lines):
        line = lines[i].strip()
        line_norm = norm(line)

        # ── Handle ### / #### section/concept headers ──────────────────────────
        if re.match(r'^#{3,4}\s+', line):
            if "THE MIRROR" in line_norm:
                flush_concept(); current_concept = None
                current_section = "synthesis"; in_mirror = True; in_map = False
                i += 1; continue
            if "THE MAP" in line_norm:
                current_section = "synthesis"; in_mirror = False; in_map = True
                i += 1; continue
            if "YOUR EMOTIONAL STRENGTHS" in line_norm:
                flush_concept(); current_concept = None
                current_section = "emotional"
                current_strength_section = result["emotional_strengths"]
                i += 1; continue
            if "YOUR SPIRITUAL STRENGTHS" in line_norm:
                flush_concept(); current_concept = None
                current_section = "spiritual"
                current_strength_section = result["spiritual_strengths"]
                i += 1; continue
            if "YOUR CREATIVE STRENGTHS" in line_norm:
                flush_concept(); current_concept = None
                current_section = "creative"
                current_strength_section = result["creative_strengths"]
                i += 1; continue
            if "WHAT IS QUIETLY BLOCKING YOU" in line_norm:
                flush_concept(); current_concept = None
                current_section = "blocking"
                i += 1; continue
            if "NEXT STEPS" in line_norm:
                flush_concept(); current_concept = None
                current_section = "next_steps"
                i += 1; continue
            if "YOUR CONTRIBUTION PATHWAYS" in line_norm:
                flush_concept(); current_concept = None
                current_section = "contribution_pathways"
                i += 1; continue
            if "YOUR INCOME CONCEPTS" in line_norm or "YOUR SYNTHESIS" in line_norm:
                flush_concept(); current_concept = None
                current_section = "concepts" if "INCOME" in line_norm else "synthesis"
                i += 1; continue
            # Unknown ### line = concept, pathway, or strength title
            flush_concept()
            current_concept = {"title": line.lstrip('#').strip(), "subsections": {}}
            if current_section in ("emotional", "spiritual", "creative"):
                current_concept["_strength_body_lines"] = []
            elif current_section != "contribution_pathways":
                current_section = "concepts"
            i += 1; continue

        # ── Old-style section detection (non-### format, fallback) ─────────────
        if "YOUR INCOME CONCEPTS" in line_norm and "VALIDATED" in line_norm:
            flush_concept(); current_concept = None
            current_section = "concepts"; i += 1; continue
        if "YOUR SYNTHESIS" in line_norm and not is_known_section(line_norm.replace("YOUR SYNTHESIS","")):
            flush_concept(); current_concept = None
            current_section = "synthesis"; i += 1; continue
        if "YOUR EMOTIONAL STRENGTHS" in line_norm and not re.match(r'^###', line):
            current_section = "emotional"
            current_strength_section = result["emotional_strengths"]
            i += 1; continue
        if "YOUR SPIRITUAL STRENGTHS" in line_norm and not re.match(r'^###', line):
            current_section = "spiritual"
            current_strength_section = result["spiritual_strengths"]
            i += 1; continue
        if "YOUR CREATIVE STRENGTHS" in line_norm and not re.match(r'^###', line):
            current_section = "creative"
            current_strength_section = result["creative_strengths"]
            i += 1; continue
        if "WHAT IS QUIETLY BLOCKING YOU" in line_norm and not re.match(r'^###', line):
            current_section = "blocking"; i += 1; continue
        if line_norm == "NEXT STEPS" and not re.match(r'^###', line):
            current_section = "next_steps"; i += 1; continue

        # ── Labeled block within concept: **Label:** text ──────────────────────
        if current_section == "concepts" and current_concept is not None:
            label_match = re.match(r'^\*\*([^*:]+):\*\*\s*(.*)', line)
            if label_match:
                label = label_match.group(1).strip()
                content_lines = [label_match.group(2).strip()]
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if not next_line:
                        # Look ahead: stop only if next non-blank is a new label or header
                        k = j + 1
                        while k < len(lines) and not lines[k].strip():
                            k += 1
                        if k < len(lines):
                            peek = lines[k].strip()
                            if (re.match(r'^\*\*[^*:]+:\*\*', peek) or
                                re.match(r'^#{3,4}', peek)):
                                break
                        j += 1; continue
                    if re.match(r'^\*\*[^*:]+:\*\*', next_line):
                        break
                    if re.match(r'^#{3,4}', next_line):
                        break
                    content_lines.append(next_line)
                    j += 1
                current_concept["subsections"][label] = plain_text(" ".join(content_lines))
                i = j; continue

        # ── Synthesis ──────────────────────────────────────────────────────────
        if current_section == "synthesis":
            mirror_match = re.match(r'^\*\*THE MIRROR:\*\*\s*(.*)', line)
            if mirror_match and not result["synthesis"]["mirror"]:
                result["synthesis"]["mirror"] = plain_text(mirror_match.group(1))
                in_mirror = True; in_map = False
            elif re.match(r'^\*\*THE MAP:\*\*', line):
                in_mirror = False; in_map = True
            elif in_mirror and line and not result["synthesis"]["mirror"]:
                result["synthesis"]["mirror"] = plain_text(line)
            elif in_map:
                bullet_match = re.match(r'^[-*\d.]+\s+(.*)', line)
                if bullet_match:
                    result["synthesis"]["map"].append(plain_text(bullet_match.group(1)))

        # ── Strengths ──────────────────────────────────────────────────────────
        # Markdown format: "Your most dominant X strength is **The Title**. body..."
        # followed by optional continuation paragraphs, shadow side, then WHAT AI WON'T DO FOR YOU
        if current_section in ("emotional", "spiritual", "creative") and current_strength_section is not None:
            if not line:
                i += 1; continue

            # Skip "WHAT AI WON'T DO FOR YOU" header and its explanation paragraph
            if "WHAT AI WON" in line_norm and "DO FOR YOU" in line_norm:
                i += 1
                while i < len(lines) and lines[i].strip():
                    i += 1
                continue

            # Accumulate body for ### / #### strength entries
            if current_concept is not None and "_strength_body_lines" in current_concept:
                current_concept["_strength_body_lines"].append(plain_text(line))
                i += 1; continue

            # **Title:** body format (most common Claude output for strengths)
            bold_title_match = re.match(r'^\*\*([^*:]+)[:\*]\*?\*?\s*(.*)', line)
            if bold_title_match and "WHAT AI WON" not in bold_title_match.group(1).upper():
                title = bold_title_match.group(1).strip().rstrip(':')
                body_lines = [plain_text(bold_title_match.group(2))] if bold_title_match.group(2) else []
                j = i + 1
                while j < len(lines):
                    nl = lines[j].strip()
                    if not nl:
                        j += 1; continue
                    if re.match(r'^#{3,4}', nl):
                        break
                    if re.match(r'^\*\*[^*:]+[:\*]', nl):
                        break
                    if "WHAT AI WON" in nl.upper() and "DO FOR YOU" in nl.upper():
                        j += 1
                        while j < len(lines) and lines[j].strip():
                            j += 1
                        break
                    body_lines.append(plain_text(nl))
                    j += 1
                current_strength_section.append({
                    "title": title,
                    "body": " ".join(b for b in body_lines if b)
                })
                i = j; continue

            # Legacy: "...strength is **The Title**..."
            strength_intro = re.search(r'strength is \*\*([^*]+)\*\*', line, re.IGNORECASE)
            if strength_intro:
                title = strength_intro.group(1).strip()
                body_lines = [plain_text(line)]
                j = i + 1
                while j < len(lines):
                    nl = lines[j].strip()
                    if not nl:
                        j += 1; continue
                    if re.match(r'^#{3,4}', nl):
                        break
                    if "WHAT AI WON" in nl.upper() and "DO FOR YOU" in nl.upper():
                        j += 1
                        while j < len(lines) and lines[j].strip():
                            j += 1
                        break
                    body_lines.append(plain_text(nl))
                    j += 1
                current_strength_section.append({
                    "title": title,
                    "body": " ".join(body_lines)
                })
                i = j; continue

        # ── Blocking patterns ──────────────────────────────────────────────────
        if current_section == "blocking":
            block_match = re.match(r'^\*\*([^*]+)\*\*[:\s]+(.*)', line)
            if block_match and "WHAT AI WON'T" not in block_match.group(1).upper():
                title = block_match.group(1).strip()
                body_lines = [block_match.group(2).strip()]
                j = i + 1
                while j < len(lines):
                    nl = lines[j].strip()
                    if not nl: break
                    if re.match(r'^\*\*', nl): break
                    body_lines.append(nl)
                    j += 1
                result["blocking_patterns"].append({
                    "title": title,
                    "body": plain_text(" ".join(body_lines))
                })
                i = j; continue

        # ── Next steps ─────────────────────────────────────────────────────────
        if current_section == "next_steps":
            if line == "[DISCOVERY_CALL_BUTTON]":
                i += 1; continue
            bullet_match = re.match(r'^[-*\d.]+\s+(.*)', line)
            if bullet_match:
                result["next_steps"].append(plain_text(bullet_match.group(1)))
            elif line and not result["next_steps"]:
                result["next_steps_intro"] = plain_text(line)
            elif line and result["next_steps"]:
                result["next_steps_closing"] = plain_text(line)

        # ── Intro paragraphs ───────────────────────────────────────────────────
        if current_section == "intro" and line and not re.match(r'^###', line) and not re.match(r'^-\s+\[', line):
            result["intro_paragraphs"].append(plain_text(line))

        i += 1

    flush_concept()
    return result


def parse_free_blueprint(md):
    """
    Parse Free Blueprint markdown into structured dict.
    Sections: intro, Where You're Already Free,
              Where You Need Support Right Now, Your Action Plan
    """
    result = {
        "intro": "",
        "already_free": "",
        "need_support": "",
        "action_steps": [],
    }

    lines = md.split('\n')
    current_section = "intro"
    intro_lines = []
    already_free_lines = []
    need_support_lines = []

    for line in lines:
        stripped = line.strip()
        norm = stripped.upper()

        if "WHERE YOU'RE ALREADY FREE" in norm or "WHERE YOU ARE ALREADY FREE" in norm:
            current_section = "already_free"
            continue
        if "WHERE YOU NEED SUPPORT" in norm:
            current_section = "need_support"
            continue
        if "YOUR ACTION PLAN" in norm:
            current_section = "action_plan"
            continue

        if current_section == "intro" and stripped:
            intro_lines.append(plain_text(stripped))
        elif current_section == "already_free" and stripped:
            already_free_lines.append(plain_text(stripped))
        elif current_section == "need_support" and stripped:
            need_support_lines.append(plain_text(stripped))
        elif current_section == "action_plan" and stripped:
            # Steps: **Bold first sentence.** rest of paragraph
            step_match = re.match(r'^\*\*(.+?)\*\*\s*(.*)', stripped)
            if step_match:
                result["action_steps"].append({
                    "bold": plain_text(step_match.group(1)),
                    "body": plain_text(step_match.group(2))
                })

    result["intro"]        = " ".join(intro_lines)
    result["already_free"] = " ".join(already_free_lines)
    result["need_support"] = " ".join(need_support_lines)
    return result

# ── PDF Component Builders ────────────────────────────────────────────────────

def concept_card(concept):
    """Build a concept card from parsed subsections as a flat list of flowables."""
    title = concept.get("title","")
    subs  = concept.get("subsections", {})
    keys  = list(subs.keys())
    use_two_col = len(keys) <= 4

    elements = []

    # Title row
    title_tbl = Table([[Paragraph(title, S["concept_title"])]], colWidths=[6.6*inch])
    title_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), WHITE),
        ("LEFTPADDING",  (0,0),(-1,-1), 14),
        ("RIGHTPADDING", (0,0),(-1,-1), 14),
        ("TOPPADDING",   (0,0),(-1,-1), 14),
        ("BOTTOMPADDING",(0,0),(-1,-1), 8),
        ("LINEBELOW",    (0,0),(-1,-1), 0.5, CARD_BORDER),
        ("LINEABOVE",    (0,0),(-1,-1), 0.5, CARD_BORDER),
        ("LINEBEFORE",   (0,0),(0,-1),  3,   GOLD),
        ("LINEAFTER",    (0,0),(-1,-1), 0.5, CARD_BORDER),
    ]))
    elements.append(KeepTogether([title_tbl]))

    if use_two_col:
        for i in range(0, len(keys), 2):
            lk = keys[i]
            rk = keys[i+1] if i+1 < len(keys) else None
            bg = CREAM if (i//2) % 2 == 0 else CREAM_DARK
            left  = [Paragraph(lk.upper(), S["sub_label"]), Paragraph(subs[lk], S["sub_text"])]
            right = [Paragraph(rk.upper() if rk else "", S["sub_label"]),
                     Paragraph(subs.get(rk,"") if rk else "", S["sub_text"])]
            row_tbl = Table([[left, right]], colWidths=[3.25*inch, 3.25*inch])
            row_tbl.setStyle(TableStyle([
                ("BACKGROUND",   (0,0),(-1,-1), bg),
                ("VALIGN",       (0,0),(-1,-1), "TOP"),
                ("LEFTPADDING",  (0,0),(-1,-1), 10),
                ("RIGHTPADDING", (0,0),(-1,-1), 10),
                ("TOPPADDING",   (0,0),(-1,-1), 8),
                ("BOTTOMPADDING",(0,0),(-1,-1), 8),
                ("LINEBEFORE",   (0,0),(0,-1),  3, GOLD),
                ("LINEAFTER",    (0,0),(-1,-1), 0.5, CARD_BORDER),
            ]))
            elements.append(row_tbl)
    else:
        for idx, key in enumerate(keys):
            bg = CREAM if idx % 2 == 0 else CREAM_DARK
            is_last = (idx == len(keys) - 1)
            row_tbl = Table([[
                Paragraph(key.upper(), S["sub_label"]),
                Paragraph(subs[key], S["sub_text"]),
            ]], colWidths=[1.4*inch, 5.2*inch])
            style = [
                ("BACKGROUND",   (0,0),(-1,-1), bg),
                ("VALIGN",       (0,0),(-1,-1), "TOP"),
                ("LEFTPADDING",  (0,0),(0,0),   12),
                ("LEFTPADDING",  (1,0),(1,-1),  10),
                ("RIGHTPADDING", (0,0),(-1,-1), 12),
                ("TOPPADDING",   (0,0),(-1,-1), 8),
                ("BOTTOMPADDING",(0,0),(-1,-1), 8),
                ("LINEBEFORE",   (0,0),(0,-1),  3, GOLD),
                ("LINEAFTER",    (0,0),(-1,-1), 0.5, CARD_BORDER),
            ]
            if is_last:
                style.append(("LINEBELOW", (0,0),(-1,-1), 0.5, CARD_BORDER))
            row_tbl.setStyle(TableStyle(style))
            elements.append(row_tbl)

    return elements

def synthesis_block(mirror, map_items):
    rows = [
        [Paragraph("YOUR SYNTHESIS  \u2022  THE MIRROR", S["synthesis_label"])],
        [Paragraph(f'\u201c{mirror}\u201d', S["synthesis_quote"])],
        [sp(0.05)],
        [Paragraph("THE MAP", S["synthesis_label"])],
    ]
    for item in map_items:
        rows += [[Paragraph(f"\u2022  {item}", S["synthesis_text"])], [sp(0.04)]]
    tbl = Table(rows, colWidths=[6.6*inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), PLUM),
        ("LEFTPADDING",  (0,0),(-1,-1), 20),
        ("RIGHTPADDING", (0,0),(-1,-1), 20),
        ("TOPPADDING",   (0,0),(0,0),   20),
        ("BOTTOMPADDING",(0,-1),(-1,-1),20),
        ("TOPPADDING",   (0,1),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-2), 4),
        ("ROUNDEDCORNERS",[4]),
    ]))
    return KeepTogether([tbl, sp(0.15)])

def strength_card(title, body, section_label):
    rows = [
        [Paragraph(section_label, S["strength_label"])],
        [Paragraph(title, S["strength_title"])],
        [Paragraph(body,  S["strength_text"])],
    ]
    tbl = Table(rows, colWidths=[6.6*inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), WHITE),
        ("LEFTPADDING",  (0,0),(-1,-1), 16),
        ("RIGHTPADDING", (0,0),(-1,-1), 16),
        ("TOPPADDING",   (0,0),(0,0),   14),
        ("BOTTOMPADDING",(0,-1),(-1,-1),14),
        ("TOPPADDING",   (0,1),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-2), 4),
        ("BOX",          (0,0),(-1,-1), 0.5, PLUM_BORDER),
        ("LINEBEFORE",   (0,0),(0,-1),  2,   PLUM_BORDER),
        ("ROUNDEDCORNERS",[4]),
    ]))
    return KeepTogether([tbl, sp(0.15)])

def blocking_card(title, body):
    rows = [
        [Paragraph(title, S["blocking_title"])],
        [Paragraph(body,  S["blocking_text"])],
    ]
    tbl = Table(rows, colWidths=[6.6*inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), CREAM_DARK),
        ("LEFTPADDING",  (0,0),(-1,-1), 14),
        ("RIGHTPADDING", (0,0),(-1,-1), 14),
        ("TOPPADDING",   (0,0),(0,0),   12),
        ("BOTTOMPADDING",(0,-1),(-1,-1),12),
        ("TOPPADDING",   (0,1),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-2), 4),
        ("BOX",          (0,0),(-1,-1), 0.5, CARD_BORDER),
        ("ROUNDEDCORNERS",[4]),
    ]))
    return KeepTogether([tbl, sp(0.12)])

def narrative_card(label, text):
    """Soft cream card for Where Already Free / Where Need Support."""
    rows = [
        [Paragraph(label.upper(), S["section_label"])],
        [Paragraph(text, S["narrative"])],
    ]
    tbl = Table(rows, colWidths=[6.6*inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), WHITE),
        ("LEFTPADDING",  (0,0),(-1,-1), 16),
        ("RIGHTPADDING", (0,0),(-1,-1), 16),
        ("TOPPADDING",   (0,0),(0,0),   14),
        ("BOTTOMPADDING",(0,-1),(-1,-1),14),
        ("TOPPADDING",   (0,1),(-1,-1), 6),
        ("BOTTOMPADDING",(0,0),(-1,-2), 6),
        ("BOX",          (0,0),(-1,-1), 0.5, CARD_BORDER),
        ("LINEBEFORE",   (0,0),(0,-1),  3,   GOLD),
        ("ROUNDEDCORNERS",[4]),
    ]))
    return KeepTogether([tbl, sp(0.15)])

def action_step(step, number=None):
    """Action plan step with gold circle dot bullet, bold sentence + explanation."""
    num_cell = Table([[Paragraph("\u2022", ParagraphStyle("gc",
        fontName=_font("Poppins-Medium"), fontSize=13, textColor=WHITE,
        alignment=TA_CENTER, leading=16))]],
        colWidths=[0.28*inch], rowHeights=[0.28*inch])
    num_cell.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), GOLD),
        ("LEFTPADDING",  (0,0),(-1,-1), 0),
        ("RIGHTPADDING", (0,0),(-1,-1), 0),
        ("TOPPADDING",   (0,0),(-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1), 0),
        ("ROUNDEDCORNERS",[14]),
    ]))

    text_content = [Paragraph(step["bold"], S["action_bold"])]
    if step.get("body"):
        text_content.append(Paragraph(step["body"], S["action_body"]))

    text_cell = Table([[p] for p in text_content], colWidths=[5.9*inch])
    text_cell.setStyle(TableStyle([
        ("LEFTPADDING",  (0,0),(-1,-1), 0),
        ("RIGHTPADDING", (0,0),(-1,-1), 0),
        ("TOPPADDING",   (0,0),(-1,-1), 0),
        ("BOTTOMPADDING",(0,0),(-1,-1), 0),
    ]))

    row = Table([[num_cell, text_cell]], colWidths=[0.45*inch, 5.9*inch])
    row.setStyle(TableStyle([
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0),(-1,-1), 0),
        ("RIGHTPADDING", (0,0),(-1,-1), 0),
        ("TOPPADDING",   (0,0),(-1,-1), 0),
        ("BOTTOMPADDING",(0,0),(-1,-1), 0),
        ("BACKGROUND",   (0,0),(-1,-1), CREAM),
        ("LEFTPADDING",  (0,0),(0,-1),  10),
        ("RIGHTPADDING", (0,0),(-1,-1), 10),
        ("TOPPADDING",   (0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("BOX",          (0,0),(-1,-1), 0.5, CARD_BORDER),
        ("LINEBEFORE",   (0,0),(0,-1),  3,   GOLD),
        ("ROUNDEDCORNERS",[4]),
    ]))
    return KeepTogether([row, sp(0.1)])

from reportlab.platypus.doctemplate import BaseDocTemplate, PageTemplate, Frame
from reportlab.lib.units import inch as _inch

def make_doc(output_path):
    W, H = letter
    margin = 0.75 * _inch

    # First page: full bleed (no margins so canvas cover fills the page)
    first_frame = Frame(0, 0, W, H, leftPadding=0, bottomPadding=0,
                        rightPadding=0, topPadding=0, id='first')
    # Later pages: normal margins
    later_frame = Frame(margin, margin, W - 2*margin, H - 2*margin,
                        id='normal')

    doc = BaseDocTemplate(output_path, pagesize=letter)
    doc.addPageTemplates([
        PageTemplate(id='First',  frames=[first_frame]),
        PageTemplate(id='Later',  frames=[later_frame]),
    ])
    return doc

# ── Builder: Freedom Blueprint ────────────────────────────────────────────────
def build_freedom_blueprint(data, output_path):
    md = data.get("blueprintMarkdown","")
    parsed = parse_free_blueprint(md)

    story = []
    story.extend(cover_page(data))

    # Intro
    if parsed["intro"]:
        story.append(sp(0.25))
        story.append(Paragraph(parsed["intro"], S["intro_text"]))
        story.append(sp(0.15))
        story.append(HRFlowable(width="100%", thickness=0.5, color=CARD_BORDER, spaceAfter=0))

    # Where Already Free
    if parsed["already_free"]:
        story.append(sp(0.1))
        story.append(narrative_card("Where You're Already Free", parsed["already_free"]))

    # Where Need Support
    if parsed["need_support"]:
        story.append(narrative_card("Where You Need Support Right Now", parsed["need_support"]))

    # Income Concepts - use rich conceptValidation if available, else fall back
    concept_validations = data.get("conceptValidation", [])
    if concept_validations:
        build_with_concept_validation(
            story, concept_validations,
            "YOUR INCOME CONCEPTS", "Built from your story."
        )
    else:
        # Fallback: basic concept cards from income assessment table data
        income_result_text = ""
        if data.get("assessments"):
            for a in data["assessments"]:
                if a.get("assessment_name") == "income-freedom-builder":
                    r = a.get("result", "")
                    income_result_text = r if isinstance(r, str) else str(r)
                    break
        if income_result_text:
            income_parsed = parse_income_builder(income_result_text)
            if income_parsed["concepts"]:
                story.append(KeepTogether([
                    Paragraph("YOUR INCOME CONCEPTS", S["section_label"]),
                    Paragraph("Built from your story.", S["section_heading"]),
                ]))
                for idx, concept in enumerate(income_parsed["concepts"]):
                    mapped = {
                        "title": concept["title"],
                        "subsections": {}
                    }
                    if concept.get("viability"):
                        mapped["subsections"]["Viability"] = concept["viability"]
                    if concept.get("who"):
                        mapped["subsections"]["Who it lights up"] = concept["who"]
                    if concept.get("price"):
                        mapped["subsections"]["Price range"] = concept["price"]
                    if concept.get("energy"):
                        mapped["subsections"]["Energy is in"] = concept["energy"]
                    if concept.get("narrative"):
                        mapped["subsections"]["How to start"] = concept["narrative"][:300]
                    if idx > 0:
                        story.append(hr(GOLD, 1.5, 8, 8))
                    story.extend(concept_card(mapped))
                    story.append(sp(0.1))

    # Action Plan - Fix 3: keep label with first step
    if parsed["action_steps"]:
        story.append(KeepTogether([
            Paragraph("YOUR ACTION PLAN", S["section_label"]),
            sp(0.08),
            action_step(parsed["action_steps"][0], 1),
        ]))
        for idx, step in enumerate(parsed["action_steps"][1:], 2):
            story.append(action_step(step, idx))

    story.extend(closing_block())
    make_doc(output_path).build(story)
    print(f"Freedom Blueprint PDF: {output_path}")

# ── Builder: Enhanced Blueprint ───────────────────────────────────────────────
def build_enhanced_blueprint(data, output_path):
    md = data.get("blueprintMarkdown","")
    parsed = parse_enhanced_blueprint(md)

    story = []
    story.extend(cover_page(data))

    name = data.get("stripe_first_name","") or data.get("name","")
    first_name = name.split()[0] if name else "you"
    business_intent = data.get("businessIntent", "")
    contribution_path = business_intent in ("Maybe someday, but it's not my focus right now", "No — my contribution isn't about income")

    # If Claude labeled them "YOUR INCOME CONCEPTS" but user is on contribution path,
    # move parsed concepts into contribution_pathways so they render with the right label.
    if contribution_path and parsed["concepts"] and not parsed["contribution_pathways"]:
        parsed["contribution_pathways"] = parsed["concepts"]
        parsed["concepts"] = []
    if contribution_path:
        warm_intro = (
            f"You showed up and answered honestly. That takes more courage than most people realize. "
            f"What follows is built entirely from what {first_name} shared — "
            f"your strengths, your patterns, and where your contribution is most likely waiting to be expressed. "
            f"Read it carefully, more than once. This is your full picture on paper."
        )
    else:
        warm_intro = (
            f"You showed up and answered honestly. That takes more courage than most people realize. "
            f"What follows is built entirely from what {first_name} shared — "
            f"your strengths, your patterns, and where your income freedom is most likely waiting. "
            f"Read it carefully, more than once. This is your full picture on paper."
        )
    intro_rows = [
        [Paragraph(warm_intro, S["intro_text"])],
        [sp(0.08)],
        [Paragraph("To your freedom,", ParagraphStyle("tf", fontName=_font("Poppins-Light"),
            fontSize=11, textColor=BODY_TEXT, leading=16))],
        [Paragraph("Cynthia", ParagraphStyle("sig", fontName=_font("Lora-Italic"),
            fontSize=16, textColor=PLUM, leading=20))],
    ]
    intro_tbl = Table(intro_rows, colWidths=[6.6*inch])
    intro_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), WHITE),
        ("LEFTPADDING",  (0,0),(-1,-1), 20),
        ("RIGHTPADDING", (0,0),(-1,-1), 20),
        ("TOPPADDING",   (0,0),(0,0),   20),
        ("BOTTOMPADDING",(0,-1),(-1,-1),20),
        ("TOPPADDING",   (0,1),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-2), 4),
        ("BOX",          (0,0),(-1,-1), 0.5, CARD_BORDER),
        ("ROUNDEDCORNERS",[4]),
    ]))
    story.append(sp(0.2))
    story.append(intro_tbl)
    story.append(sp(0.2))

    # Personalized intro paragraphs from the blueprint markdown
    if parsed["intro_paragraphs"]:
        for para in parsed["intro_paragraphs"]:
            story.append(Paragraph(para, S["narrative"]))
            story.append(sp(0.08))

    story.append(HRFlowable(width="100%", thickness=0.5, color=CARD_BORDER, spaceAfter=0))

    # Contribution Pathways (non-business branch)
    if parsed["contribution_pathways"]:
        story.append(KeepTogether([
            sp(0.1),
            Paragraph("YOUR CONTRIBUTION PATHWAYS", S["section_label"]),
            Paragraph("How your gifts are meant to reach the world.", S["section_heading"]),
        ]))
        for idx, pathway in enumerate(parsed["contribution_pathways"]):
            if idx > 0:
                story.append(PageBreak())
            story.extend(concept_card(pathway))
            story.append(sp(0.1))

    # Income Concepts (business branch) - prefer parsed markdown, fall back to conceptValidation
    elif parsed["concepts"]:
        story.append(KeepTogether([
            sp(0.1),
            Paragraph("YOUR INCOME CONCEPTS", S["section_label"]),
            Paragraph("Built from your story.", S["section_heading"]),
        ]))
        for idx, concept in enumerate(parsed["concepts"]):
            if idx > 0:
                story.append(PageBreak())
            story.extend(concept_card(concept))
            story.append(sp(0.1))
    else:
        concept_validations = data.get("conceptValidation", [])
        if concept_validations:
            build_with_concept_validation(
                story, concept_validations,
                "YOUR INCOME CONCEPTS", "Built from your story."
            )

    story.append(sp(0.1))

    # Synthesis
    if parsed["synthesis"]["mirror"]:
        story.append(synthesis_block(parsed["synthesis"]["mirror"], parsed["synthesis"]["map"]))

    # Fix 8: Section headings with strong visual anchor - cream band behind label
    def section_anchor(label, subhead):
        """Cream background band that visually anchors a section heading."""
        rows = [
            [Paragraph(label, S["section_label"])],
            [Paragraph(subhead, S["section_heading_lg"])],
        ]
        tbl = Table(rows, colWidths=[6.6*inch])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), CREAM_DARK),
            ("LEFTPADDING",  (0,0),(-1,-1), 14),
            ("RIGHTPADDING", (0,0),(-1,-1), 14),
            ("TOPPADDING",   (0,0),(0,0),   12),
            ("BOTTOMPADDING",(0,-1),(-1,-1),12),
            ("TOPPADDING",   (0,1),(-1,-1), 2),
            ("BOTTOMPADDING",(0,0),(-1,-2), 2),
            ("LINEBEFORE",   (0,0),(0,-1),  3, GOLD),
        ]))
        return tbl

    # Emotional Strengths
    if parsed["emotional_strengths"]:
        story.append(KeepTogether([
            section_anchor("YOUR EMOTIONAL STRENGTHS", "What drives you forward."),
            sp(0.1),
            strength_card(parsed["emotional_strengths"][0]["title"],
                         parsed["emotional_strengths"][0]["body"],
                         "Dominant Emotional Strength"),
        ]))
        for s in parsed["emotional_strengths"][1:]:
            story.append(strength_card(s["title"], s["body"], "Dominant Emotional Strength"))

    # Spiritual Strengths
    if parsed["spiritual_strengths"]:
        story.append(KeepTogether([
            section_anchor("YOUR SPIRITUAL STRENGTHS", "Where your purpose lives."),
            sp(0.1),
            strength_card(parsed["spiritual_strengths"][0]["title"],
                         parsed["spiritual_strengths"][0]["body"],
                         "Dominant Spiritual Strength"),
        ]))
        for s in parsed["spiritual_strengths"][1:]:
            story.append(strength_card(s["title"], s["body"], "Dominant Spiritual Strength"))

    # Creative Strengths
    if parsed["creative_strengths"]:
        story.append(KeepTogether([
            section_anchor("YOUR CREATIVE STRENGTHS", "The gifts you were born with."),
            sp(0.1),
            strength_card(parsed["creative_strengths"][0]["title"],
                         parsed["creative_strengths"][0]["body"],
                         "Dominant Creative Strength"),
        ]))
        for s in parsed["creative_strengths"][1:]:
            story.append(strength_card(s["title"], s["body"], "Dominant Creative Strength"))

    # Blocking Patterns
    if parsed["blocking_patterns"]:
        story.append(KeepTogether([
            section_anchor("WHAT IS QUIETLY BLOCKING YOU", "Patterns worth knowing about."),
            sp(0.1),
            blocking_card(parsed["blocking_patterns"][0]["title"],
                         parsed["blocking_patterns"][0]["body"]),
        ]))
        for b in parsed["blocking_patterns"][1:]:
            story.append(blocking_card(b["title"], b["body"]))

    # Next Steps
    if parsed["next_steps"] or parsed["next_steps_intro"] or parsed["next_steps_closing"]:
        story.append(KeepTogether([
            section_anchor("YOUR NEXT STEPS", "Where to begin."),
            sp(0.1),
        ]))
        if parsed["next_steps_intro"]:
            story.append(Paragraph(parsed["next_steps_intro"], S["narrative"]))
            story.append(sp(0.08))
        for idx, step in enumerate(parsed["next_steps"], 1):
            story.append(KeepTogether([
                Table([[
                    Table([[Paragraph("\u2022", ParagraphStyle("gc2",
                        fontName=_font("Poppins-Medium"), fontSize=13, textColor=WHITE,
                        alignment=TA_CENTER, leading=16))]],
                        colWidths=[0.28*inch], rowHeights=[0.28*inch],
                        style=[("BACKGROUND",(0,0),(-1,-1),GOLD),
                               ("TOPPADDING",(0,0),(-1,-1),3),
                               ("LEFTPADDING",(0,0),(-1,-1),0),
                               ("RIGHTPADDING",(0,0),(-1,-1),0),
                               ("BOTTOMPADDING",(0,0),(-1,-1),0),
                               ("ROUNDEDCORNERS",[14])]),
                    Paragraph(step, S["next_step_bold"]),
                ]], colWidths=[0.45*inch, 5.9*inch],
                style=[("VALIGN",(0,0),(-1,-1),"TOP"),
                       ("LEFTPADDING",(0,0),(-1,-1),8),
                       ("RIGHTPADDING",(0,0),(-1,-1),8),
                       ("TOPPADDING",(0,0),(-1,-1),8),
                       ("BOTTOMPADDING",(0,0),(-1,-1),8),]),
                sp(0.08)
            ]))
        if parsed["next_steps_closing"]:
            story.append(sp(0.08))
            story.append(Paragraph(parsed["next_steps_closing"], S["narrative"]))

    story.extend(closing_block())
    make_doc(output_path).build(story)
    print(f"Enhanced Blueprint PDF: {output_path}")

# ── Builder: Income Freedom Builder ──────────────────────────────────────────
def build_income_builder(data, output_path):
    """
    Income Builder uses structured data fields directly
    (not markdown parsing) since it comes from the income assessment result.
    """
    story = []
    story.extend(cover_page(data))

    if data.get("intro"):
        story.append(sp(0.25))
        story.append(Paragraph(data["intro"], S["intro_text"]))
        story.append(sp(0.15))
        story.append(HRFlowable(width="100%", thickness=0.5, color=CARD_BORDER, spaceAfter=0))

    # Viability score block
    if data.get("viability_score"):
        rows = [
            [Paragraph("VIABILITY SCORE", S["sub_label"])],
            [Paragraph(data["viability_score"], S["ib_score"])],
            [Paragraph(data.get("viability_text",""), S["sub_text"])],
        ]
        tbl = Table(rows, colWidths=[6.6*inch])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), CREAM_DARK),
            ("LEFTPADDING",  (0,0),(-1,-1), 16),
            ("RIGHTPADDING", (0,0),(-1,-1), 16),
            ("TOPPADDING",   (0,0),(0,0),   14),
            ("BOTTOMPADDING",(0,-1),(-1,-1),14),
            ("TOPPADDING",   (0,1),(-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-2), 4),
            ("BOX",          (0,0),(-1,-1), 0.5, CARD_BORDER),
            ("LINEBEFORE",   (0,0),(0,-1),  3,   GOLD),
            ("ROUNDEDCORNERS",[4]),
        ]))
        story.append(KeepTogether([tbl, sp(0.15)]))

    # Buyer profile
    if data.get("buyer_profile"):
        rows = [[Paragraph(f'\u201c{data["buyer_profile"]}\u201d', S["ib_buyer"])]]
        tbl = Table(rows, colWidths=[6.6*inch])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), WHITE),
            ("LEFTPADDING",  (0,0),(-1,-1), 20),
            ("RIGHTPADDING", (0,0),(-1,-1), 20),
            ("TOPPADDING",   (0,0),(0,0),   16),
            ("BOTTOMPADDING",(0,-1),(-1,-1),16),
            ("BOX",          (0,0),(-1,-1), 0.5, CARD_BORDER),
            ("ROUNDEDCORNERS",[4]),
        ]))
        story.append(KeepTogether([tbl, sp(0.15)]))

    # Pricing range
    if data.get("pricing_range"):
        rows = [
            [Paragraph("PRICING RANGE", S["sub_label"])],
            [Paragraph(data["pricing_range"], S["ib_price"])],
            [Paragraph(data.get("pricing_text",""), S["sub_text"])],
        ]
        tbl = Table(rows, colWidths=[6.6*inch])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), WHITE),
            ("LEFTPADDING",  (0,0),(-1,-1), 16),
            ("RIGHTPADDING", (0,0),(-1,-1), 16),
            ("TOPPADDING",   (0,0),(0,0),   14),
            ("BOTTOMPADDING",(0,-1),(-1,-1),14),
            ("TOPPADDING",   (0,1),(-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-2), 4),
            ("BOX",          (0,0),(-1,-1), 0.5, CARD_BORDER),
            ("ROUNDEDCORNERS",[4]),
        ]))
        story.append(KeepTogether([tbl, sp(0.15)]))

    # Concepts
    if data.get("concepts"):
        story.append(Paragraph("YOUR INCOME CONCEPTS", S["section_label"]))
        story.append(Paragraph("These paths are built from your story.", S["section_heading"]))
        for c in data["concepts"]:
            story.extend(concept_card(c))
            story.append(sp(0.15))

    if data.get("what_i_notice"):
        rows = [
            [Paragraph("WHAT I NOTICE", S["sub_label"])],
            [Paragraph(data["what_i_notice"], S["sub_text"])],
        ]
        tbl = Table(rows, colWidths=[6.6*inch])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), CREAM_DARK),
            ("LEFTPADDING",  (0,0),(-1,-1), 16),
            ("RIGHTPADDING", (0,0),(-1,-1), 16),
            ("TOPPADDING",   (0,0),(0,0),   14),
            ("BOTTOMPADDING",(0,-1),(-1,-1),14),
            ("TOPPADDING",   (0,1),(-1,-1), 6),
            ("BOTTOMPADDING",(0,0),(-1,-2), 6),
            ("BOX",          (0,0),(-1,-1), 0.5, CARD_BORDER),
            ("ROUNDEDCORNERS",[4]),
        ]))
        story.append(KeepTogether([tbl, sp(0.15)]))

    story.extend(closing_block())
    make_doc(output_path).build(story)
    print(f"Income Builder PDF: {output_path}")

# ── Main Entry Point ──────────────────────────────────────────────────────────
def generate_pdf(data, output_path=None):
    pdf_type   = data.get("type","blueprint")
    session_id = data.get("sessionId","output")
    if not output_path:
        output_path = f"/tmp/fa40_{pdf_type}_{session_id}.pdf"
    if pdf_type == "income":
        build_income_builder(data, output_path)
    elif pdf_type == "blueprint":
        build_freedom_blueprint(data, output_path)
    elif pdf_type == "enhanced":
        build_enhanced_blueprint(data, output_path)
    else:
        raise ValueError(f"Unknown type: {pdf_type}")
    return output_path

# ── Test with real sample files ───────────────────────────────────────────────
if __name__ == "__main__":
    out = "/mnt/user-data/outputs"

    # Test Freedom Blueprint with real markdown
    with open("/mnt/user-data/uploads/sample_free_blueprint.md") as f:
        free_md = f.read()
    build_freedom_blueprint({
        "type": "blueprint",
        "email": "jane@example.com",
        "blueprintMarkdown": free_md,
    }, f"{out}/FA40_Freedom_Blueprint_Sample.pdf")

    # Test Enhanced Blueprint with real markdown
    with open("/mnt/user-data/uploads/sample_enhanced_blueprint__1_.md") as f:
        enhanced_md = f.read()
    build_enhanced_blueprint({
        "type": "enhanced",
        "stripe_first_name": "Jane",
        "stripe_last_name": "Mitchell",
        "blueprintMarkdown": enhanced_md,
    }, f"{out}/FA40_Enhanced_Blueprint_Sample.pdf")

    print("Done. Income Builder requires structured data from webhook.")

# ── Income Builder Parser ─────────────────────────────────────────────────────

def parse_income_builder(result_text):
    """
    Parse the income-freedom-builder result markdown into structured dict.
    Result is stored as an escaped string in assessment_results.result field.
    """
    # Unescape literal \n sequences from JSON storage
    text = result_text.strip()
    if '\\n' in text:
        text = text.replace('\\n', '\n')
    result = {
        "your_idea": "",
        "opening": "",
        "viability_score": "",
        "viability_text": "",
        "buyer_profile": "",
        "pricing_range": "",
        "pricing_text": "",
        "market_observation": "",
        "concepts": [],
        "what_i_notice": "",
    }

    lines = text.split('\n')
    i = 0

    # Extract Your Idea line
    if lines and lines[0].startswith("Your Idea:"):
        result["your_idea"] = plain_text(lines[0].replace("Your Idea:", "").strip())
        i = 1

    # Collect opening paragraph
    opening_lines = []
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r'^Viability Score:', line, re.IGNORECASE):
            break
        if line:
            opening_lines.append(plain_text(line))
        i += 1
    result["opening"] = " ".join(opening_lines)

    # Viability Score
    while i < len(lines):
        line = lines[i].strip()
        vs_match = re.match(r'^Viability Score:\s*(.+)', line, re.IGNORECASE)
        if vs_match:
            result["viability_score"] = plain_text(vs_match.group(1))
            i += 1
            # Next non-empty line is viability text
            while i < len(lines):
                vt = lines[i].strip()
                if vt and not re.match(r'^Your future buyer', vt, re.IGNORECASE):
                    result["viability_text"] = plain_text(vt)
                    i += 1
                    break
                elif vt:
                    break
                i += 1
            break
        i += 1

    # Buyer profile
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r'^Your future buyer', line, re.IGNORECASE):
            buyer_lines = [plain_text(line)]
            i += 1
            while i < len(lines):
                nl = lines[i].strip()
                if not nl or re.match(r'^Pricing Range:', nl, re.IGNORECASE):
                    break
                buyer_lines.append(plain_text(nl))
                i += 1
            result["buyer_profile"] = " ".join(buyer_lines)
            break
        i += 1

    # Pricing Range
    while i < len(lines):
        line = lines[i].strip()
        pr_match = re.match(r'^Pricing Range:\s*(.+)', line, re.IGNORECASE)
        if pr_match:
            result["pricing_range"] = plain_text(pr_match.group(1))
            i += 1
            pricing_text_lines = []
            while i < len(lines):
                nl = lines[i].strip()
                if not nl or re.match(r'^The current market', nl, re.IGNORECASE) or re.match(r'^Three Concepts', nl, re.IGNORECASE):
                    break
                pricing_text_lines.append(plain_text(nl))
                i += 1
            result["pricing_text"] = " ".join(pricing_text_lines)
            break
        i += 1

    # Market observation
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r'^The current market', line, re.IGNORECASE):
            market_lines = [plain_text(line)]
            i += 1
            while i < len(lines):
                nl = lines[i].strip()
                if not nl or re.match(r'^Three Concepts', nl, re.IGNORECASE):
                    break
                market_lines.append(plain_text(nl))
                i += 1
            result["market_observation"] = " ".join(market_lines)
            break
        i += 1

    # Parse markdown table for concepts
    in_table = False
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r'^\|', line):
            in_table = True
            # Skip header and divider rows
            if re.match(r'^\|\s*:?-', line) or re.match(r'^\|\s*Concept', line, re.IGNORECASE):
                i += 1
                continue
            # Parse concept row
            cells = [c.strip() for c in line.strip('|').split('|')]
            if len(cells) >= 5 and cells[0] and not cells[0].startswith(':'):
                result["concepts"].append({
                    "title":      plain_text(cells[0]),
                    "viability":  plain_text(cells[1]) if len(cells) > 1 else "",
                    "who":        plain_text(cells[2]) if len(cells) > 2 else "",
                    "price":      plain_text(cells[3]) if len(cells) > 3 else "",
                    "energy":     plain_text(cells[4]) if len(cells) > 4 else "",
                    "narrative":  "",
                })
        elif in_table and line:
            in_table = False
        i += 1

    # Match narrative paragraphs to concepts by name
    concept_names = [c["title"].lower() for c in result["concepts"]]
    current_concept_idx = None
    narrative_lines = []

    i = 0
    in_narrative = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if "What I Notice" in stripped or "What I notice" in stripped:
            if current_concept_idx is not None and narrative_lines:
                result["concepts"][current_concept_idx]["narrative"] = plain_text(" ".join(narrative_lines))
            current_concept_idx = None
            narrative_lines = []
            in_narrative = "what_i_notice"
            continue
        if in_narrative == "what_i_notice":
            result["what_i_notice"] += plain_text(stripped) + " "
            continue
        # Check if line matches a concept title
        matched = False
        for idx, name in enumerate(concept_names):
            key_words = name.split()[:3]
            if all(kw.lower() in stripped.lower() for kw in key_words if len(kw) > 3):
                if current_concept_idx is not None and narrative_lines:
                    result["concepts"][current_concept_idx]["narrative"] = plain_text(" ".join(narrative_lines))
                current_concept_idx = idx
                narrative_lines = []
                matched = True
                break
        if not matched and current_concept_idx is not None and stripped and not re.match(r'^\|', stripped):
            narrative_lines.append(stripped)

    if current_concept_idx is not None and narrative_lines:
        result["concepts"][current_concept_idx]["narrative"] = plain_text(" ".join(narrative_lines))

    result["what_i_notice"] = result["what_i_notice"].strip()
    return result


# ── Income Builder PDF Builders ───────────────────────────────────────────────

def three_col_concept_cards(concepts):
    """Three side-by-side summary cards for Income Builder."""
    if not concepts:
        return []

    col_w = (6.6 * inch - 0.2 * inch) / 3  # three equal columns with small gap

    cells = []
    for concept in concepts[:3]:  # max 3 side by side
        cell_rows = [
            [Paragraph(concept["title"], S["concept_title"])],
            [Paragraph(concept.get("viability",""), S["concept_meta"])],
            [HRFlowable(width="100%", thickness=0.5, color=CARD_BORDER, spaceAfter=4, spaceBefore=4)],
        ]
        for label, key in [("Who it lights up", "who"), ("Price range", "price"), ("Energy is in", "energy")]:
            val = concept.get(key, "")
            if val:
                cell_rows.append([Paragraph(label.upper(), S["sub_label"])])
                cell_rows.append([Paragraph(val, S["sub_text"])])
                cell_rows.append([sp(0.04)])

        cell_tbl = Table(cell_rows, colWidths=[col_w - 0.25*inch])
        cell_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), WHITE),
            ("LEFTPADDING",  (0,0),(-1,-1), 10),
            ("RIGHTPADDING", (0,0),(-1,-1), 10),
            ("TOPPADDING",   (0,0),(0,0),   12),
            ("BOTTOMPADDING",(0,-1),(-1,-1),12),
            ("TOPPADDING",   (0,1),(-1,-1), 3),
            ("BOTTOMPADDING",(0,0),(-1,-2), 3),
            ("BOX",          (0,0),(-1,-1), 0.5, CARD_BORDER),
            ("LINEABOVE",    (0,0),(-1,0),  3,   GOLD),
            ("ROUNDEDCORNERS",[4]),
        ]))
        cells.append(cell_tbl)

    # Pad to 3 if fewer
    while len(cells) < 3:
        cells.append(Spacer(col_w, 0.1))

    row = Table([cells], colWidths=[col_w, col_w, col_w])
    row.setStyle(TableStyle([
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0),(-1,-1), 4),
        ("RIGHTPADDING", (0,0),(-1,-1), 4),
        ("TOPPADDING",   (0,0),(-1,-1), 0),
        ("BOTTOMPADDING",(0,0),(-1,-1), 0),
    ]))
    return [row, sp(0.15)]


VIABILITY_DEF = "Your viability score reflects how well this concept matches your skills, the current market demand, and your realistic path to first revenue. 10 is the strongest possible match."

def viability_block(score, text):
    rows = [
        [Paragraph("VIABILITY SCORE", S["sub_label"])],
        [Paragraph(score, S["ib_score"])],
        [Paragraph(text, S["sub_text"])],
        [sp(0.04)],
        [Paragraph(VIABILITY_DEF, S["viability_def"])],
    ]
    tbl = Table(rows, colWidths=[6.6*inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), CREAM_DARK),
        ("LEFTPADDING",  (0,0),(-1,-1), 16),
        ("RIGHTPADDING", (0,0),(-1,-1), 16),
        ("TOPPADDING",   (0,0),(0,0),   14),
        ("BOTTOMPADDING",(0,-1),(-1,-1),14),
        ("TOPPADDING",   (0,1),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-2), 4),
        ("BOX",          (0,0),(-1,-1), 0.5, CARD_BORDER),
        ("LINEBEFORE",   (0,0),(0,-1),  3,   GOLD),
        ("ROUNDEDCORNERS",[4]),
    ]))
    return [KeepTogether([tbl, sp(0.15)])]


def buyer_block(text):
    rows = [[Paragraph(f'\u201c{text}\u201d', S["ib_buyer"])]]
    tbl = Table(rows, colWidths=[6.6*inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), WHITE),
        ("LEFTPADDING",  (0,0),(-1,-1), 20),
        ("RIGHTPADDING", (0,0),(-1,-1), 20),
        ("TOPPADDING",   (0,0),(0,0),   16),
        ("BOTTOMPADDING",(0,-1),(-1,-1),16),
        ("BOX",          (0,0),(-1,-1), 0.5, CARD_BORDER),
        ("ROUNDEDCORNERS",[4]),
    ]))
    return [KeepTogether([tbl, sp(0.15)])]


def pricing_block(price, text):
    rows = [
        [Paragraph("PRICING RANGE", S["sub_label"])],
        [Paragraph(price, S["ib_price"])],
        [Paragraph(text, S["sub_text"])],
    ]
    tbl = Table(rows, colWidths=[6.6*inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), WHITE),
        ("LEFTPADDING",  (0,0),(-1,-1), 16),
        ("RIGHTPADDING", (0,0),(-1,-1), 16),
        ("TOPPADDING",   (0,0),(0,0),   14),
        ("BOTTOMPADDING",(0,-1),(-1,-1),14),
        ("TOPPADDING",   (0,1),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-2), 4),
        ("BOX",          (0,0),(-1,-1), 0.5, CARD_BORDER),
        ("ROUNDEDCORNERS",[4]),
    ]))
    return [KeepTogether([tbl, sp(0.15)])]


def what_i_notice_block(text):
    rows = [
        [Paragraph("WHAT I NOTICE", S["sub_label"])],
        [Paragraph(text, S["sub_text"])],
    ]
    tbl = Table(rows, colWidths=[6.6*inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), CREAM_DARK),
        ("LEFTPADDING",  (0,0),(-1,-1), 16),
        ("RIGHTPADDING", (0,0),(-1,-1), 16),
        ("TOPPADDING",   (0,0),(0,0),   14),
        ("BOTTOMPADDING",(0,-1),(-1,-1),14),
        ("TOPPADDING",   (0,1),(-1,-1), 6),
        ("BOTTOMPADDING",(0,0),(-1,-2), 6),
        ("BOX",          (0,0),(-1,-1), 0.5, CARD_BORDER),
        ("ROUNDEDCORNERS",[4]),
    ]))
    return [KeepTogether([tbl, sp(0.15)])]


def build_income_builder_v2(data, output_path):
    """
    Build Income Builder PDF from webhook payload.
    Expects data['assessments'] to contain the income-freedom-builder row,
    or data['incomeResult'] as a direct string.
    """
    # Extract income result from assessments array or direct field
    income_result_text = ""
    if data.get("incomeResult"):
        income_result_text = data["incomeResult"]
    elif data.get("assessments"):
        for a in data["assessments"]:
            if a.get("assessment_name") == "income-freedom-builder":
                r = a.get("result","")
                income_result_text = r if isinstance(r, str) else str(r)
                break

    if not income_result_text:
        print("Warning: no income result found in data")
        return

    parsed = parse_income_builder(income_result_text)

    story = []
    story.extend(cover_page(data))

    # Opening
    if parsed["opening"]:
        story.append(sp(0.25))
        story.append(Paragraph(parsed["opening"], S["intro_text"]))
        story.append(sp(0.15))
        story.append(HRFlowable(width="100%", thickness=0.5, color=CARD_BORDER, spaceAfter=0))

    # Your Idea - same Option B card style as generated concepts, labeled distinctly
    your_idea_text = ""
    if data.get("assessments"):
        for a in data["assessments"]:
            if a.get("assessment_name") == "income-freedom-builder":
                your_idea_text = a.get("responses", {}).get("existingIdea", "")
                break
    if not your_idea_text:
        your_idea_text = parsed["your_idea"]

    if your_idea_text:
        idea_cell_rows = [
            [Paragraph("YOUR IDEA", S["sub_label"])],
            [Paragraph(plain_text(your_idea_text), S["concept_title"])],
            [HRFlowable(width="100%", thickness=0.5, color=CARD_BORDER, spaceAfter=4, spaceBefore=6)],
        ]
        if parsed["viability_score"]:
            idea_cell_rows.append([Paragraph("VIABILITY SCORE", S["sub_label"])])
            idea_cell_rows.append([Paragraph(parsed["viability_score"], S["sub_text"])])
            idea_cell_rows.append([Paragraph(VIABILITY_DEF, S["viability_def"])])
            idea_cell_rows.append([sp(0.04)])
        if parsed["pricing_range"]:
            idea_cell_rows.append([Paragraph("PRICING RANGE", S["sub_label"])])
            idea_cell_rows.append([Paragraph(parsed["pricing_range"], S["sub_text"])])
            idea_cell_rows.append([sp(0.04)])

        idea_tbl = Table(idea_cell_rows, colWidths=[6.6*inch])
        idea_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), WHITE),
            ("LEFTPADDING",  (0,0),(-1,-1), 14),
            ("RIGHTPADDING", (0,0),(-1,-1), 14),
            ("TOPPADDING",   (0,0),(0,0),   14),
            ("BOTTOMPADDING",(0,-1),(-1,-1),14),
            ("TOPPADDING",   (0,1),(-1,-1), 3),
            ("BOTTOMPADDING",(0,0),(-1,-2), 3),
            ("BOX",          (0,0),(-1,-1), 0.5, CARD_BORDER),
            ("LINEABOVE",    (0,0),(-1,0),  3,   GOLD),
            ("ROUNDEDCORNERS",[4]),
        ]))
        story.append(KeepTogether([idea_tbl, sp(0.15)]))

    # Buyer profile as standalone italic quote (not duplicated)
    if parsed["buyer_profile"]:
        story.extend(buyer_block(parsed["buyer_profile"]))

    # Market observation - styled in plum/gold to stand out
    if parsed["market_observation"]:
        rows = [[Paragraph(parsed["market_observation"], S["market_energy"])]]
        tbl = Table(rows, colWidths=[6.6*inch])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), CREAM_DARK),
            ("LEFTPADDING",  (0,0),(-1,-1), 16),
            ("RIGHTPADDING", (0,0),(-1,-1), 16),
            ("TOPPADDING",   (0,0),(0,0),   12),
            ("BOTTOMPADDING",(0,-1),(-1,-1),12),
            ("LINEBEFORE",   (0,0),(0,-1),  3, GOLD),
            ("BOX",          (0,0),(-1,-1), 0.5, CARD_BORDER),
            ("ROUNDEDCORNERS",[4]),
        ]))
        story.append(KeepTogether([tbl, sp(0.12)]))

    # Three AI-generated concept cards - Fix gap: keep label with cards
    if parsed["concepts"]:
        cards = three_col_concept_cards(parsed["concepts"])
        story.append(KeepTogether([
            Paragraph("THREE CONCEPTS BUILT FOR YOU", S["section_label"]),
            Paragraph("These paths are built from your story.", S["section_heading"]),
            cards[0],  # the row table
        ]))
        if len(cards) > 1:
            story.extend(cards[1:])

    # What I Notice
    if parsed["what_i_notice"]:
        story.extend(what_i_notice_block(parsed["what_i_notice"]))

    story.extend(closing_block())
    make_doc(output_path).build(story)
    print(f"Income Builder PDF: {output_path}")


# ── Concept Validation Card (rich per-concept sections) ───────────────────────

def concept_validation_card(cv, show_viability_def=False):
    """
    Build a rich concept card from ConceptValidation JSON object.
    Fields: name, isUserIdea, viabilityScore, targetAudience,
            marketDemand, freedomFilterScore, freedomFilterMeaning,
            realityCheck, validationQuestions[], nextStep
    """
    title = cv.get("name", "")
    is_user_idea = cv.get("isUserIdea", False)
    viability = cv.get("viabilityScore", "")
    pricing = cv.get("pricing", "")

    elements = []

    # Title header row
    label_text = "YOUR IDEA" if is_user_idea else ""
    header_rows = []
    if label_text:
        header_rows.append([Paragraph(label_text, S["sub_label"])])
    header_rows.append([Paragraph(title, S["concept_title"])])
    if viability or pricing:
        meta_parts = []
        if viability: meta_parts.append(f"Viability: {viability}")
        if pricing:   meta_parts.append(pricing)
        header_rows.append([Paragraph("   |   ".join(meta_parts), S["concept_meta"])])
    if show_viability_def:
        header_rows.append([Paragraph(VIABILITY_DEF, S["viability_def"])])

    title_tbl = Table(header_rows, colWidths=[6.6*inch])
    title_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), WHITE),
        ("LEFTPADDING",  (0,0),(-1,-1), 14),
        ("RIGHTPADDING", (0,0),(-1,-1), 14),
        ("TOPPADDING",   (0,0),(0,0),   14),
        ("BOTTOMPADDING",(0,-1),(-1,-1),10),
        ("TOPPADDING",   (0,1),(-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-2), 3),
        ("LINEABOVE",    (0,0),(-1,0),  3,   GOLD),
        ("LINEBELOW",    (0,-1),(-1,-1),0.5, CARD_BORDER),
        ("LINEBEFORE",   (0,0),(0,-1),  0.5, CARD_BORDER),
        ("LINEAFTER",    (0,0),(-1,-1), 0.5, CARD_BORDER),
    ]))
    elements.append(title_tbl)

    # Body sections - alternating cream/cream-dark
    sections = [
        ("WHO IT LIGHTS UP",            cv.get("targetAudience","")),
        ("MARKET DEMAND FOR THIS CONCEPT", cv.get("marketDemand","")),
        (f"FREEDOM FILTER: {cv.get('freedomFilterScore','')}",
                                         cv.get("freedomFilterMeaning","")),
    ]

    for idx, (label, body) in enumerate(sections):
        if not body: continue
        bg = CREAM if idx % 2 == 0 else CREAM_DARK
        row_tbl = Table([
            [Paragraph(label, S["sub_label"])],
            [Paragraph(plain_text(body), S["sub_text"])],
        ], colWidths=[6.6*inch])
        row_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), bg),
            ("LEFTPADDING",  (0,0),(-1,-1), 14),
            ("RIGHTPADDING", (0,0),(-1,-1), 14),
            ("TOPPADDING",   (0,0),(0,0),   8),
            ("BOTTOMPADDING",(0,-1),(-1,-1),8),
            ("TOPPADDING",   (0,1),(-1,-1), 3),
            ("BOTTOMPADDING",(0,0),(-1,-2), 3),
            ("LINEBEFORE",   (0,0),(0,-1),  0.5, CARD_BORDER),
            ("LINEAFTER",    (0,0),(-1,-1), 0.5, CARD_BORDER),
        ]))
        elements.append(row_tbl)

    # Reality Check - italic callout
    reality = cv.get("realityCheck","")
    if reality:
        rc_tbl = Table([
            [Paragraph("REALITY CHECK", S["sub_label"])],
            [Paragraph(plain_text(reality), ParagraphStyle("rc",
                fontName=_font("Poppins-Light"), fontSize=11, textColor=BODY_TEXT,
                leading=17, fontStyle="italic"))],
        ], colWidths=[6.6*inch])
        rc_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), CREAM_DARK),
            ("LEFTPADDING",  (0,0),(-1,-1), 14),
            ("RIGHTPADDING", (0,0),(-1,-1), 14),
            ("TOPPADDING",   (0,0),(0,0),   8),
            ("BOTTOMPADDING",(0,-1),(-1,-1),8),
            ("TOPPADDING",   (0,1),(-1,-1), 3),
            ("BOTTOMPADDING",(0,0),(-1,-2), 3),
            ("LINEBEFORE",   (0,0),(0,-1),  0.5, CARD_BORDER),
            ("LINEAFTER",    (0,0),(-1,-1), 0.5, CARD_BORDER),
        ]))
        elements.append(rc_tbl)

    # Validation Questions
    questions = cv.get("validationQuestions", [])
    if questions:
        q_rows = [[Paragraph("3 VALIDATION QUESTIONS", S["sub_label"])]]
        for i, q in enumerate(questions, 1):
            q_rows.append([Paragraph(f"{i}. {plain_text(q)}", S["sub_text"])])
        q_tbl = Table(q_rows, colWidths=[6.6*inch])
        q_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), CREAM),
            ("LEFTPADDING",  (0,0),(-1,-1), 14),
            ("RIGHTPADDING", (0,0),(-1,-1), 14),
            ("TOPPADDING",   (0,0),(0,0),   8),
            ("BOTTOMPADDING",(0,-1),(-1,-1),8),
            ("TOPPADDING",   (0,1),(-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-2), 4),
            ("LINEBEFORE",   (0,0),(0,-1),  0.5, CARD_BORDER),
            ("LINEAFTER",    (0,0),(-1,-1), 0.5, CARD_BORDER),
        ]))
        elements.append(q_tbl)

    # Your Next Step - gold accent
    next_step = cv.get("nextStep","")
    if next_step:
        ns_tbl = Table([
            [Paragraph("YOUR NEXT STEP", S["sub_label"])],
            [Paragraph(plain_text(next_step), S["sub_text"])],
        ], colWidths=[6.6*inch])
        ns_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), WHITE),
            ("LEFTPADDING",  (0,0),(-1,-1), 14),
            ("RIGHTPADDING", (0,0),(-1,-1), 14),
            ("TOPPADDING",   (0,0),(0,0),   8),
            ("BOTTOMPADDING",(0,-1),(-1,-1),12),
            ("TOPPADDING",   (0,1),(-1,-1), 3),
            ("BOTTOMPADDING",(0,0),(-1,-2), 3),
            ("LINEBELOW",    (0,-1),(-1,-1),0.5, CARD_BORDER),
            ("LINEBEFORE",   (0,0),(0,-1),  3,   GOLD),
            ("LINEAFTER",    (0,0),(-1,-1), 0.5, CARD_BORDER),
        ]))
        elements.append(ns_tbl)

    return elements


def build_with_concept_validation(story, concept_validations, section_label_text, section_heading_text):
    """
    Render a full set of concept validation cards with section header.
    Used by both Freedom Blueprint and Enhanced Blueprint builders.
    """
    if not concept_validations:
        return

    first_cv = concept_validations[0]
    first_card = concept_validation_card(first_cv, show_viability_def=True)

    story.append(KeepTogether([
        Paragraph(section_label_text, S["section_label"]),
        Paragraph(section_heading_text, S["section_heading"]),
        first_card[0],
    ]))
    story.extend(first_card[1:])
    story.append(sp(0.1))

    for cv in concept_validations[1:]:
        story.append(sp(0.1))
        story.append(HRFlowable(width="100%", thickness=2, color=GOLD,
            spaceBefore=4, spaceAfter=4))
        story.append(sp(0.05))
        story.extend(concept_validation_card(cv))
        story.append(sp(0.1))

