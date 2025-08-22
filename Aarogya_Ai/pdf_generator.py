import os
import io
import json
from datetime import datetime
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
    name = user_data.get("name", "Not provided")
    age = user_data.get("age", "Not provided")
    gender = user_data.get("gender", "Not specified")
    symptoms = user_data.get("symptoms", "No symptoms recorded")

    lines: List[str] = []
    lines.append("You are a medical expert AI. Based on the provided patient information, generate a comprehensive health analysis report.")
    lines.append("")
    lines.append("IMPORTANT: Provide accurate, specific medical information based on the symptoms. Be precise and informative.")
    lines.append("")
    lines.append("Patient Information:")
    lines.append("- Patient Name")
    lines.append("- Patient Age") 
    lines.append("- Patient Gender")
    lines.append("- Reported Symptoms")
    lines.append("")
    lines.append("Analysis Requirements:")
    lines.append("1. Provide detailed symptoms analysis explaining how reported symptoms relate to the predicted condition")
    lines.append("2. Give specific, accurate risks if the condition is left untreated")
    lines.append("3. Consider patient's age and gender for personalized recommendations")
    lines.append("4. Provide evidence-based medical information")
    lines.append("")
    lines.append("Return ONLY valid JSON in this exact format:")
    lines.append("")
    lines.append("{")
    lines.append('  "gender": "string",')
    lines.append('  "predicted_disease": "string - most likely condition based on symptoms",')
    lines.append('  "confidence_level": "number between 0.70 and 0.95 representing diagnostic confidence based on symptom clarity and specificity",')
    lines.append('  "description": "detailed medical description of the condition",')
    lines.append('  "symptoms_analysis": "2-3 line concise explanation of how the reported symptoms relate to the predicted condition",')
    lines.append('  "risks_if_untreated": "2-3 line specific medical risks if this condition is not treated",')
    lines.append('  "recommended_medicines": [')
    lines.append('    {"name": "medicine name 1", "dosage": "age-appropriate dosage", "notes": "administration notes"},')
    lines.append('    {"name": "medicine name 2", "dosage": "age-appropriate dosage", "notes": "administration notes"},')
    lines.append('    {"name": "medicine name 3", "dosage": "age-appropriate dosage", "notes": "administration notes"}')
    lines.append('  ],')
    lines.append('  "suggested_diet": ["specific dietary recommendation 1", "specific dietary recommendation 2"],')
    lines.append('  "workout_exercise": ["age and condition appropriate exercise 1", "age and condition appropriate exercise 2"]')
    lines.append("}")
    lines.append("")
    lines.append("Critical Rules:")
    lines.append('- confidence_level: Provide a realistic confidence score (0.70-0.95) based on how well symptoms match the condition')
    lines.append('- symptoms_analysis: MAXIMUM 2-3 lines explaining symptom correlation')
    lines.append('- risks_if_untreated: MAXIMUM 2-3 lines of specific medical risks')
    lines.append('- recommended_medicines: MUST provide exactly 3 medicines with proper names, dosages, and notes')
    lines.append('- Provide real medicine names commonly used for the predicted condition')
    lines.append('- Keep all explanations concise and focused')
    lines.append('- Consider age for medication dosing and exercise recommendations')
    lines.append('- Consider gender for condition-specific advice when relevant')
    lines.append('- Do NOT use generic templates - provide specific but brief analysis')
    lines.append('- Return ONLY JSON, no markdown, no explanations, no code blocks')
    lines.append("")
    lines.append("Patient Details:")
    lines.append(f"- Name: {name}")
    lines.append(f"- Age: {age}")
    lines.append(f"- Gender: {gender}")
    lines.append(f"- Reported symptoms: {symptoms}")
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
        "gender": user_data.get("gender") or "Not specified",
        "predicted_disease": user_data.get("predicted_disease") or "Undetermined",
        "confidence_level": 0.75,  # Default confidence level
        "description": f"Medical analysis for {user_data.get('name', 'patient')} requires further evaluation.",
        "symptoms_analysis": f"The reported symptoms ({user_data.get('symptoms', 'none provided')}) need medical assessment for accurate diagnosis.",
        "risks_if_untreated": "Consult healthcare professional for risk assessment and proper treatment guidance.",
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

    # Patient Information Section
    story.append(Paragraph("Patient Information", styles["SectionHeader"]))
    story.append(Spacer(1, 0.08 * inch))
    
    # Get current date for report
    report_date = datetime.now().strftime("%B %d, %Y")
    
    # Create patient info table
    patient_data = [
        ["Name:", report.get("name", "Not provided")],
        ["Age:", str(report.get("age", "Not provided"))],
        ["Gender:", report.get("gender", "Not specified")],
        ["Contact:", report.get("contact", "Not provided")],
        ["Reported Symptoms:", report.get("symptoms", "No symptoms recorded")],
        ["Report Date:", report_date]
    ]
    
    patient_table = Table(patient_data, colWidths=[2*inch, 4*inch])
    patient_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(patient_table)
    story.append(Spacer(1, 0.2 * inch))

    # Medical Analysis Section
    predicted = report.get("predicted_disease", "Undetermined")
    confidence = report.get("confidence_level", 0.75)
    
    story.append(Paragraph("Medical Analysis", styles["SectionHeader"]))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(f"<b>Predicted Condition:</b> {predicted}", styles["NormalGray"]))
    story.append(Spacer(1, 0.05 * inch))
    
    # Add confidence level with color coding
    confidence_percentage = f"{confidence * 100:.1f}%" if isinstance(confidence, (int, float)) else "75.0%"
    confidence_color = "#28a745" if confidence >= 0.85 else "#ffc107" if confidence >= 0.75 else "#dc3545"
    
    story.append(Paragraph(f"<b>Diagnostic Confidence:</b> <font color='{confidence_color}'>{confidence_percentage}</font>", styles["NormalGray"]))
    story.append(Spacer(1, 0.05 * inch))
    
    # Add confidence explanation
    if confidence >= 0.85:
        confidence_note = "High confidence - Symptoms strongly indicate this condition"
    elif confidence >= 0.75:
        confidence_note = "Moderate confidence - Symptoms suggest this condition, but consider other possibilities"
    else:
        confidence_note = "Lower confidence - Multiple conditions possible, further evaluation recommended"
    
    story.append(Paragraph(f"<i>{confidence_note}</i>", styles["NormalGray"]))
    story.append(Spacer(1, 0.15 * inch))

    # Clinical Description
    description = report.get("description", "")
    if description:
        story.append(Paragraph("Clinical Description", styles["SectionHeader"]))
        story.append(Spacer(1, 0.08 * inch))
        story.append(Paragraph(description, styles["NormalGray"]))
        story.append(Spacer(1, 0.15 * inch))

    # Symptoms Analysis - AI Generated
    symptoms_analysis = report.get("symptoms_analysis", "")
    if symptoms_analysis:
        story.append(Paragraph("Symptoms Analysis", styles["SectionHeader"]))
        story.append(Spacer(1, 0.08 * inch))
        story.append(Paragraph(symptoms_analysis, styles["NormalGray"]))
        story.append(Spacer(1, 0.15 * inch))

    # Risk Assessment - AI Generated
    risks_untreated = report.get("risks_if_untreated", "")
    if risks_untreated:
        story.append(Paragraph("Risks if Untreated", styles["SectionHeader"]))
        story.append(Spacer(1, 0.08 * inch))
        story.append(Paragraph(risks_untreated, styles["NormalGray"]))
        story.append(Spacer(1, 0.15 * inch))

    # Recommended Medicines - Enhanced formatting
    medicines: List[Dict[str, str]] = report.get("recommended_medicines") or []
    if medicines:
        story.append(Paragraph("Recommended Medicines", styles["SectionHeader"]))
        story.append(Spacer(1, 0.08 * inch))
        
        for i, med in enumerate(medicines, 1):
            med_name = med.get("name", f"Medicine {i}")
            med_dosage = med.get("dosage", "As prescribed")
            med_notes = med.get("notes", "Follow doctor's guidance")
            
            # Format with bold medicine name
            medicine_text = f"• <b>{med_name}</b> - {med_dosage}"
            if med_notes and med_notes != "As prescribed" and med_notes != "Follow doctor's guidance":
                medicine_text += f" ({med_notes})"
            
            story.append(Paragraph(medicine_text, styles["NormalGray"]))
        
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
        user_data: Dict with user information including name, age, contact, gender, symptoms, etc.

    Returns:
        (pdf_bytes, filename)
    """
    ai_response: Dict[str, Any] = _call_gemini(user_data)

    report_merged = {
        # User personal information
        "name": user_data.get("name", "Not provided"),
        "age": user_data.get("age", "Not provided"),
        "contact": user_data.get("contact", "Not provided"),
        "gender": ai_response.get("gender") or user_data.get("gender") or "Not specified",
        
        # Symptom information
        "symptoms": user_data.get("symptoms", "No symptoms recorded"),
        
        # Medical analysis from AI
        "predicted_disease": ai_response.get("predicted_disease") or user_data.get("predicted_disease") or "Undetermined",
        "description": ai_response.get("description") or user_data.get("analysis_summary", ""),
        
        # Enhanced AI analysis sections
        "symptoms_analysis": ai_response.get("symptoms_analysis", "No detailed symptoms analysis available."),
        "risks_if_untreated": ai_response.get("risks_if_untreated", "Risk assessment not available."),
        
        # Treatment recommendations
        "recommended_medicines": ai_response.get("recommended_medicines") or [],
        "suggested_diet": ai_response.get("suggested_diet") or [],
        "workout_exercise": ai_response.get("workout_exercise") or []
    }

    pdf_bytes = build_pdf(report_merged)
    
    # Generate filename with user name if available
    user_name = user_data.get("name", "").replace(" ", "_") if user_data.get("name") != "Not provided" else "user"
    predicted_condition = report_merged.get("predicted_disease", "report").replace(" ", "_")
    filename = f"{user_name}_symptom_report_{predicted_condition}.pdf"
    
    return pdf_bytes, filename



