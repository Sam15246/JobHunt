"""Generate a one-page PDF resume from plain text.

Uses ReportLab to create a clean, professional PDF matching the style of
the candidate's existing resume: single column, clear section headings,
bullet points, compact spacing.
"""
import os
import logging
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
)
from reportlab.lib.colors import HexColor

logger = logging.getLogger(__name__)

TAILORED_DIR = os.path.join(os.path.dirname(__file__), "..", "resumes", "tailored")

# Margins and page setup
PAGE_MARGIN_TOP = 12 * mm
PAGE_MARGIN_BOTTOM = 12 * mm
PAGE_MARGIN_SIDE = 14 * mm


def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="ResumeName",
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=17,
        alignment=TA_CENTER,
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="ResumeTagline",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        alignment=TA_CENTER,
        textColor=HexColor("#444444"),
        spaceAfter=1,
    ))
    styles.add(ParagraphStyle(
        name="ResumeContact",
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=HexColor("#555555"),
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        spaceBefore=6,
        spaceAfter=2,
        textColor=HexColor("#000000"),
    ))
    styles.add(ParagraphStyle(
        name="SubHeading",
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        spaceBefore=3,
        spaceAfter=1,
    ))
    styles.add(ParagraphStyle(
        name="ResumeBody",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        spaceAfter=1,
    ))
    styles.add(ParagraphStyle(
        name="ResumeBullet",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        leftIndent=10,
        bulletIndent=0,
        spaceAfter=1,
    ))
    styles.add(ParagraphStyle(
        name="SkillLine",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        spaceAfter=0.5,
    ))
    return styles


def _parse_resume_text(text: str) -> list:
    """Parse the plain-text resume into structured blocks for PDF rendering."""
    lines = text.strip().split("\n")
    blocks = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            blocks.append(("spacer", None))
        elif stripped.startswith("- ") or stripped.startswith("* "):
            blocks.append(("bullet", stripped[2:].strip()))
        elif stripped.isupper() and len(stripped) > 3:
            blocks.append(("section", stripped))
        elif stripped.startswith("Key Project:") or stripped.startswith("Key project:"):
            blocks.append(("subheading", stripped))
        elif ":" in stripped and len(stripped.split(":")[0].split()) <= 4 and not any(c.islower() for c in stripped.split(":")[0]):
            # Lines like "Backend: Java, Spring Boot..." or "CGPA: 9.54..."
            blocks.append(("skill", stripped))
        else:
            blocks.append(("body", stripped))

    return blocks


def generate_pdf(tailored_text: str, output_path: str) -> str:
    """Generate a PDF from tailored resume text. Returns the output file path."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=PAGE_MARGIN_TOP,
        bottomMargin=PAGE_MARGIN_BOTTOM,
        leftMargin=PAGE_MARGIN_SIDE,
        rightMargin=PAGE_MARGIN_SIDE,
    )

    styles = _build_styles()
    blocks = _parse_resume_text(tailored_text)
    story = []

    is_first_line = True
    is_second_line = True

    for block_type, content in blocks:
        if block_type == "spacer":
            story.append(Spacer(1, 2 * mm))
        elif block_type == "section":
            story.append(Spacer(1, 1 * mm))
            story.append(Paragraph(content, styles["SectionHeading"]))
            story.append(HRFlowable(
                width="100%", thickness=0.5,
                color=HexColor("#999999"), spaceAfter=2,
            ))
        elif block_type == "subheading":
            story.append(Paragraph(content, styles["SubHeading"]))
        elif block_type == "bullet":
            story.append(Paragraph(
                f"\u2022 {content}",
                styles["ResumeBullet"],
            ))
        elif block_type == "skill":
            story.append(Paragraph(content, styles["SkillLine"]))
        elif block_type == "body":
            # First non-section line = name, second = tagline
            if is_first_line and content and not content.startswith(("-", "*")):
                story.append(Paragraph(content, styles["ResumeName"]))
                is_first_line = False
            elif is_second_line and not is_first_line:
                story.append(Paragraph(content, styles["ResumeTagline"]))
                is_second_line = False
            else:
                story.append(Paragraph(content, styles["ResumeBody"]))

    doc.build(story)
    logger.info(f"Generated tailored PDF: {output_path}")
    return output_path


def generate_tailored_pdf(tailored_text: str, job_id: str) -> str:
    """Convenience wrapper: saves to resumes/tailored/{job_id}.pdf."""
    os.makedirs(TAILORED_DIR, exist_ok=True)
    output_path = os.path.join(TAILORED_DIR, f"{job_id}.pdf")
    return generate_pdf(tailored_text, output_path)
