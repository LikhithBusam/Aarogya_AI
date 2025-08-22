import os
import io
import json
from typing import Any, Dict, List, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch

# Gemini API
try:
    import google.generativeai as genai
except Exception as exc:  # pragma: no cover
    genai = None


def _configure_gemini() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set.")
    if genai is None:
        raise RuntimeError("google-generativeai package is not installed. Add 'google-generativeai' to requirements.")
    genai.configure(api_key=api_key)


def _build_gemini_prompt(user_data: Dict[str, Any]) -> str:
    gender = user_data.get("gender") or "Unspecified"
    symptoms = user_data.get("symptoms") or ""
    severity = user_data.get("severity") or "not provided"

    lines: List[str] = []
    lines.append("You are a medical report generator. Based strictly on the provided input, generate a structured health report.")
    lines.append("")
    lines.append("Inputs:")
    lines.append("- User Gender")
    lines.append("- Reported Symptoms")
    lines.append("- (Optional) Severity level")
    lines.append("")
    lines.append("Rules:")
    lines.append("1. If severity is provided → consider BOTH symptoms and severity while predicting disease, medicines, diet, etc.")
    lines.append("2. If severity is not provided → base the outcome ONLY on the symptoms.")
    lines.append("3. Always return the output in the following JSON structure:")
    lines.append("")
    lines.append("{")
    lines.append('  "gender": "string",')
    lines.append('  "predicted_disease": "string",')
    lines.append('  "description": "medical description based on symptoms (and severity if provided)",')
    lines.append('  "recommended_medicines": [')
    lines.append('    {"name": "medicine name", "dosage": "dosage details", "notes": "special notes"}')
    lines.append('  ],')
    lines.append('  "suggested_diet": ["diet recommendation 1", "diet recommendation 2"],')
    lines.append('  "workout_exercise": ["exercise recommendation 1", "exercise recommendation 2"]')
    lines.append("}")
    lines.append("")
    lines.append("Formatting Rules:")
    lines.append('- "recommended_medicines" must always be a list of objects with clear "name", "dosage", and "notes".')
    lines.append('- "suggested_diet" and "workout_exercise" must be lists of bullet-point style strings.')
    lines.append('- Keep explanations short, symptom-specific, and avoid generic medical advice.')
    lines.append('- Do NOT return free text, only valid JSON (no markdown, no code fences).')
    lines.append("")
    lines.append("Patient context (use ONLY this information):")
    lines.append(f"- Gender: {gender}")
    lines.append(f"- Reported symptoms: {symptoms}")
    lines.append(f"- Severity: {severity}")
    return "\n".join(lines)


def _call_gemini(user_data: Dict[str, Any]) -> Dict[str, Any]:
    _configure_gemini()
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = _build_gemini_prompt(user_data)
    response = model.generate_content(prompt)
    text = response.text or "{}"

    # Strip code-fence if present
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.strip("`\n").split('\n', 1)[-1]

    # Extract JSON inside if any extra text sneaks in
    try:
        # Try direct parse first
        return json.loads(text)
    except Exception:
        # Fallback: find first and last curly braces block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass

    # Minimal fallback structure
    return {
        "gender": user_data.get("gender") or "Unspecified",
        "predicted_disease": user_data.get("predicted_disease") or "Undetermined",
        "description": "Insufficient information to provide a detailed description.",
        "recommended_medicines": [],
        "suggested_diet": [],
        "workout_exercise": []
    }


def _build_story(report: Dict[str, Any]) -> List[Any]:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleBlue", parent=styles["Title"], textColor=colors.HexColor("#3367d6")))
    styles.add(ParagraphStyle(name="SectionHeader", parent=styles["Heading2"], textColor=colors.HexColor("#3367d6")))
    styles.add(ParagraphStyle(name="NormalGray", parent=styles["Normal"], textColor=colors.HexColor("#333333"), leading=16))

    story: List[Any] = []

    # Title
    story.append(Paragraph("Symptom Analysis Report", styles["TitleBlue"]))
    story.append(Spacer(1, 0.15 * inch))

    # Patient summary
    gender = report.get("gender", "Unspecified")
    predicted = report.get("predicted_disease", "Undetermined")
    story.append(Paragraph("Patient Overview", styles["SectionHeader"]))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(f"<b>Gender:</b> {gender}", styles["NormalGray"]))
    story.append(Paragraph(f"<b>Predicted Disease:</b> {predicted}", styles["NormalGray"]))
    story.append(Spacer(1, 0.15 * inch))

    # Description (disease name, brief info, symptom linkage, risks)
    description = report.get("description") or ""
    predicted_disease = report.get("predicted_disease", "Undetermined")
    symptoms = report.get("symptoms", "")
    severity = report.get("severity", "")
    # Compose a structured description if not already present
    if description:
        story.append(Paragraph("Clinical Description", styles["SectionHeader"]))
        story.append(Spacer(1, 0.08 * inch))
        # If description does not follow the required format, reformat it
        # Always build the description in the required format
    disease_info = f"<b>Disease:</b> {predicted_disease}.<br/>"
    # Use model's description for 'About', fallback only if missing
    about_text = description if description.strip() else "No detailed information available for this disease."
    brief_info = f"<b>About:</b> {about_text}<br/>"
    symptom_link = f"<b>Symptoms:</b> The reported symptoms ({symptoms})" + (f" with severity {severity}" if severity else "") + f" are commonly associated with {predicted_disease}.<br/>"
    risks = f"<b>Risks if untreated:</b> Potential risks may occur if {predicted_disease} is not treated promptly.<br/>"
    description = disease_info + brief_info + symptom_link + risks
    story.append(Paragraph(description.replace("\n", "<br/>"), styles["NormalGray"]))
    story.append(Spacer(1, 0.15 * inch))

    # Allopathic and Ayurvedic recommendations
    allopathy: List[Dict[str, str]] = report.get("recommended_medicines") or []
    ayurveda: List[Dict[str, str]] = report.get("ayurvedic_remedies") or []
    if allopathy or ayurveda:
        story.append(Paragraph("Recommended Medicines", styles["SectionHeader"]))
        story.append(Spacer(1, 0.08 * inch))
        if allopathy:
            story.append(Paragraph("Allopathy:", styles["NormalGray"]))
            for med in allopathy:
                med_name = med.get("name", "-")
                med_dosage = med.get("dosage", "-")
                med_notes = med.get("notes", "-")
                bullet = f"• {med_name} {med_dosage} {med_notes}".replace("  ", " ").strip()
                story.append(Paragraph(bullet, styles["NormalGray"]))
        if ayurveda:
            story.append(Spacer(1, 0.08 * inch))
            story.append(Paragraph("Ayurveda:", styles["NormalGray"]))
            for remedy in ayurveda:
                remedy_name = remedy.get("name", "-")
                usage = remedy.get("usage", "-")
                bullet = f"• {remedy_name} ({usage})"
                story.append(Paragraph(bullet, styles["NormalGray"]))
        story.append(Spacer(1, 0.15 * inch))

    # Diet
    diet_list: List[str] = report.get("suggested_diet") or []
    if diet_list:
        story.append(Paragraph("Suggested Diet", styles["SectionHeader"]))
        story.append(Spacer(1, 0.08 * inch))
        for item in diet_list:
            story.append(Paragraph(f"• {item}", styles["NormalGray"]))
        story.append(Spacer(1, 0.15 * inch))

    # Workout / Exercise
    exercise_list: List[str] = report.get("workout_exercise") or []
    if exercise_list:
        story.append(Paragraph("Workout / Exercise", styles["SectionHeader"]))
        story.append(Spacer(1, 0.08 * inch))
        for item in exercise_list:
            story.append(Paragraph(f"• {item}", styles["NormalGray"]))
        story.append(Spacer(1, 0.15 * inch))

    return story


def build_pdf(report: Dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=48,
        leftMargin=48,
        topMargin=56,
        bottomMargin=56,
        title="Symptom Analysis Report",
        author="Aarogya AI"
    )
    story = _build_story(report)
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def generate_pdf(user_data: Dict[str, Any]) -> Tuple[bytes, str]:
    """Generate a PDF based on user data using Gemini for structured content.

    Args:
        user_data: Dict with optional keys: gender, symptoms, predicted_disease, analysis_summary

    Returns:
        (pdf_bytes, filename)
    """
    ai_response: Dict[str, Any] = _call_gemini(user_data)

    report_merged = {
        "gender": ai_response.get("gender") or user_data.get("gender") or "Unspecified",
        "predicted_disease": ai_response.get("predicted_disease") or user_data.get("predicted_disease") or "Undetermined",
        "description": ai_response.get("description") or "",
        "recommended_medicines": ai_response.get("recommended_medicines") or [],
        "suggested_diet": ai_response.get("suggested_diet") or [],
        "workout_exercise": ai_response.get("workout_exercise") or []
    }

    pdf_bytes = build_pdf(report_merged)
    predicted_for_name = report_merged.get("predicted_disease", "report").replace(" ", "_")
    filename = f"symptom_report_{predicted_for_name or 'report'}.pdf"
    return pdf_bytes, filename



