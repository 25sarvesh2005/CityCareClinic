"""
─────────────────────────────────────────────────────────────────────────────
File        : core/services/pdf_service.py
Purpose     : Dynamic PDF prescription generator using ReportLab.

Renders a high-precision medical prescription PDF with clinic header,
patient info, diagnosis, structured medication table, and doctor signature block.
─────────────────────────────────────────────────────────────────────────────
"""

import io
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from common.logger import get_logger

logger = get_logger(__name__)


def generate_prescription_pdf(
    prescription_id: str,
    hospital_name: str,
    doctor_name: str,
    specialization: str,
    clinic_address: str,
    clinic_phone: str,
    patient_name: str,
    date_str: str,
    appointment_id: str,
    diagnosis: str,
    medications: List[Dict[str, Any]],
    notes: Optional[str] = None,
    follow_up_date: Optional[str] = None,
    temperature: Optional[float] = None,
    symptoms: Optional[List[str]] = None,
) -> bytes:
    """
    Generates a professional PDF prescription document and returns raw PDF bytes.

    Args:
        prescription_id: MongoDB ObjectId string of prescription.
        hospital_name: Name of clinic/hospital.
        doctor_name: Full name of doctor.
        specialization: Doctor specialization string.
        clinic_address: Address line.
        clinic_phone: Phone contact.
        patient_name: Patient full name.
        date_str: Prescription date (YYYY-MM-DD).
        appointment_id: Associated appointment ID string.
        diagnosis: Clinical diagnosis text.
        medications: List of medication dicts (medicine_name, dosage, frequency, duration, instructions).
        notes: Doctor advice or notes.
        follow_up_date: Recommended follow-up date.
        temperature: Patient body temperature in Fahrenheit.
        symptoms: List of reported symptoms.

    Returns:
        bytes: Binary PDF file payload.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom Color Palette
    PRIMARY_COLOR = colors.HexColor("#0F172A")    # Dark slate
    SECONDARY_COLOR = colors.HexColor("#0284C7")  # Cyan/Teal accent
    TEXT_COLOR = colors.HexColor("#334155")       # Muted slate text
    LIGHT_BG = colors.HexColor("#F8FAFC")         # Very light gray
    BORDER_COLOR = colors.HexColor("#E2E8F0")     # Light border

    # Custom Typography Styles
    title_style = ParagraphStyle(
        "ClinicTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=PRIMARY_COLOR,
    )

    subtitle_style = ParagraphStyle(
        "DoctorSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=SECONDARY_COLOR,
    )

    meta_style = ParagraphStyle(
        "ClinicMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=TEXT_COLOR,
    )

    label_bold = ParagraphStyle(
        "LabelBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=PRIMARY_COLOR,
    )

    value_normal = ParagraphStyle(
        "ValueNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=TEXT_COLOR,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.white,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=TEXT_COLOR,
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=PRIMARY_COLOR,
    )

    story = []

    # ── 1. Header Section ──
    header_data = [
        [
            Paragraph(f"<b>{hospital_name}</b>", title_style),
            Paragraph(f"<b>Prescription Ref:</b> #{prescription_id[-8:].upper()}", meta_style),
        ],
        [
            Paragraph(f"{doctor_name} — <i>{specialization}</i>", subtitle_style),
            Paragraph(f"<b>Date:</b> {date_str}", meta_style),
        ],
        [
            Paragraph(f"📍 {clinic_address} | 📞 {clinic_phone}", meta_style),
            Paragraph(f"<b>Appt ID:</b> {appointment_id[-8:].upper()}", meta_style),
        ],
    ]

    header_table = Table(header_data, colWidths=[380, 160])
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=SECONDARY_COLOR, spaceBefore=2, spaceAfter=10))

    # ── 2. Patient Details & Clinical Summary Box ──
    temp_str = f"{temperature}°F" if temperature else "N/A"
    symptoms_str = ", ".join([s.title() for s in symptoms]) if symptoms else "None reported"

    patient_info_data = [
        [
            Paragraph("<b>Patient Name:</b>", label_bold),
            Paragraph(patient_name, value_normal),
            Paragraph("<b>Temperature:</b>", label_bold),
            Paragraph(temp_str, value_normal),
        ],
        [
            Paragraph("<b>Diagnosis:</b>", label_bold),
            Paragraph(f"<b>{diagnosis}</b>", value_normal),
            Paragraph("<b>Symptoms:</b>", label_bold),
            Paragraph(symptoms_str, value_normal),
        ],
    ]

    patient_table = Table(patient_info_data, colWidths=[90, 200, 90, 160])
    patient_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
            ("BOX", (0, 0), (-1, -1), 1, BORDER_COLOR),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(patient_table)
    story.append(Spacer(1, 15))

    # ── 3. Prescribed Rx Symbol & Title ──
    rx_header_data = [
        [
            Paragraph("<font size=16 color='#0284C7'><b>Rx</b></font> &nbsp; <b>PRESCRIBED MEDICATIONS</b>", section_heading)
        ]
    ]
    rx_table = Table(rx_header_data, colWidths=[540])
    rx_table.setStyle(TableStyle([("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story.append(rx_table)
    story.append(Spacer(1, 6))

    # ── 4. Medications Table ──
    med_table_data = [
        [
            Paragraph("#", table_header_style),
            Paragraph("Medicine Name", table_header_style),
            Paragraph("Dosage", table_header_style),
            Paragraph("Frequency", table_header_style),
            Paragraph("Duration", table_header_style),
            Paragraph("Instructions", table_header_style),
        ]
    ]

    for idx, med in enumerate(medications, start=1):
        med_table_data.append([
            Paragraph(str(idx), table_cell_style),
            Paragraph(f"<b>{med.get('medicine_name', '')}</b>", table_cell_style),
            Paragraph(med.get("dosage", ""), table_cell_style),
            Paragraph(med.get("frequency", ""), table_cell_style),
            Paragraph(med.get("duration", ""), table_cell_style),
            Paragraph(med.get("instructions", "") or "As advised", table_cell_style),
        ])

    med_table = Table(med_table_data, colWidths=[25, 140, 75, 100, 70, 130])
    ts = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
    ]

    # Alternating row background
    for row_idx in range(1, len(med_table_data)):
        if row_idx % 2 == 0:
            ts.append(("BACKGROUND", (0, row_idx), (-1, row_idx), LIGHT_BG))

    med_table.setStyle(TableStyle(ts))
    story.append(med_table)
    story.append(Spacer(1, 15))

    # ── 5. Notes & Advice & Follow-up ──
    if notes or follow_up_date:
        story.append(Paragraph("<b>Doctor's Advice & Notes:</b>", section_heading))
        story.append(Spacer(1, 4))

        advice_text = notes if notes else "Follow prescribed dosage instructions carefully."
        if follow_up_date:
            advice_text += f"<br/><br/><b>📅 Recommended Follow-up Date:</b> {follow_up_date}"

        advice_data = [[Paragraph(advice_text, value_normal)]]
        advice_table = Table(advice_data, colWidths=[540])
        advice_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 1, BORDER_COLOR),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ])
        )
        story.append(advice_table)
        story.append(Spacer(1, 20))

    # ── 6. Signature & Footer Block ──
    sig_data = [
        [
            Paragraph("<b>Clinic Stamp</b>", meta_style),
            Paragraph(f"<b>{doctor_name}</b><br/><i>Authorized Medical Officer</i><br/>{specialization}", ParagraphStyle("SigRight", parent=meta_style, alignment=2)),
        ]
    ]
    sig_table = Table(sig_data, colWidths=[270, 270])
    sig_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("TOPPADDING", (0, 0), (-1, -1), 20),
        ])
    )
    story.append(sig_table)
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_COLOR, spaceBefore=5, spaceAfter=5))
    story.append(
        Paragraph(
            "<i>This is an electronically generated prescription issued via CityCare Clinic Management System. Valid without manual seal.</i>",
            ParagraphStyle("Disclaimer", parent=meta_style, fontSize=8, textColor=colors.HexColor("#94A3B8"), alignment=1),
        )
    )

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    logger.info("Generated PDF prescription size=%d bytes for prescription_id=%s", len(pdf_bytes), prescription_id)
    return pdf_bytes
