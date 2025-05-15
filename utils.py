import fitz  # PyMuPDF
import json5
import re
import google.generativeai as genai
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO

REQUIRED_KEYS = [
    "StartupName", "OverallScore", "ExecutiveSummary", "Sector",
    "SectorAnalysisIndia", "TracxnStyleBenchmark", "ProductMarketFit", "GTMExecution",
    "SupplyChainOps", "BusinessModel", "FoundersEvaluation", "ExitOptions", "Comments",
    "CompetitiveLandscape", "UncertaintyAnalysis"
]

def extract_pdf_text(uploaded_file):
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    return '\n'.join([page.get_text().replace('\xa0', ' ') for page in doc])

def validate_structure(data):
    return all(k in data for k in REQUIRED_KEYS)

def analyze_pitch_deck(pitch_text, api_key, return_raw=False):
    genai.configure(api_key=api_key)
    safe_pitch_text = pitch_text[:28000].replace("```

    prompt = f"""
Generate VALID JSON for an investment scorecard with this structure:
{{
  "StartupName": string,
  "OverallScore": int,
  "ExecutiveSummary": [string],
  "Sector": string,
  "SectorAnalysisIndia": [string],
  "TracxnStyleBenchmark": {{"Key": "Value", ...}},
  "ProductMarketFit": {{"Parameter": {{"Score": int, "Rationale": [string]}, ...}}},
  "GTMExecution": {{"Parameter": {{"Score": int, "Rationale": [string]}, ...}}},
  "SupplyChainOps": {{"Parameter": {{"Score": int, "Rationale": [string]}, ...}}},
  "BusinessModel": {{"Parameter": {{"Score": int, "Rationale": [string]}, ...}}},
  "FoundersEvaluation": {{"Criteria": {{"Score": int, "Assessment": string}, ...}}},
  "ExitOptions": [string],
  "Comments": [string],
  "CompetitiveLandscape": [{{"Name": string, "USP": string, "BusinessModelAlignment": string}}],
  "UncertaintyAnalysis": [{{"Category": string, "RiskScore": int, "Rationale": string}}]
}}
Use only double quotes. Return ONLY valid JSON.
PITCH DECK:
<>
""".replace("<>", safe_pitch_text)

    model = genai.GenerativeModel("gemini-1.5-pro-latest", generation_config={
        "temperature": 0.3,
        "response_mime_type": "application/json",
        "max_output_tokens": 4000
    })

    raw_response = None
    for _ in range(3):
        try:
            response = model.generate_content(prompt)
            raw = response.text.strip()
            raw_response = raw  # Save for debugging

            # Remove code block markers if present
            raw = re.sub(r"^```json|^``````$", "", raw, flags=re.MULTILINE).strip()

            # Try to find the largest valid JSON object in the response
            json_start = raw.find("{")
            json_end = raw.rfind("}")
            if json_start != -1 and json_end != -1:
                raw = raw[json_start:json_end+1]

            data = json5.loads(raw)
            if data and validate_structure(data):
                return (data, raw_response) if return_raw else data
        except Exception:
            continue
    return (None, raw_response) if return_raw else None

def generate_scorecard_pdf(scorecard):
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=0.5 * inch, leftMargin=0.5 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    elements = []

    elements.append(Paragraph(f"Deep-Dive Scorecard: {scorecard.get('StartupName', 'N/A')}", styles['Title']))
    elements.append(Paragraph(f"Overall Score: {scorecard.get('OverallScore', 0)}/100", styles['Heading1']))

    def add_section(title, content):
        elements.append(Paragraph(title, styles['Heading2']))
        for item in content if isinstance(content, list) else [content]:
            elements.append(Paragraph(f"- {item}", styles['Normal']))
        elements.append(Spacer(1, 12))

    def add_matrix(title, section):
        elements.append(Paragraph(title, styles['Heading2']))
        data_rows = [["Parameter", "Score (/100)", "Reason"]]
        for key, val in section.items():
            rationale = val.get("Rationale", [])
            rationale_text = "<br/>".join("- " + r for r in rationale)
            data_rows.append([key, val.get("Score", ""), rationale_text])
        table = Table(data_rows, colWidths=[1.5 * inch, 1.2 * inch, 3.3 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Add sections and matrices
    add_section("Executive Summary", scorecard.get("ExecutiveSummary", []))
    add_section("Sector", scorecard.get("Sector", ""))
    add_section("Sector Analysis (India)", scorecard.get("SectorAnalysisIndia", []))
    add_section("Tracxn-Style Benchmark", [f"{k}: {v}" for k, v in scorecard.get("TracxnStyleBenchmark", {}).items()])
    add_matrix("Product Market Fit", scorecard.get("ProductMarketFit", {}))
    add_matrix("GTM Execution", scorecard.get("GTMExecution", {}))
    add_matrix("Supply Chain & Ops", scorecard.get("SupplyChainOps", {}))
    add_matrix("Business Model", scorecard.get("BusinessModel", {}))

    # Founders Evaluation Table
    founders = scorecard.get("FoundersEvaluation", {})
    if founders:
        elements.append(Paragraph("Founders Evaluation", styles['Heading2']))
        data_rows = [["Criteria", "Score", "Assessment"]]
        for key, val in founders.items():
            data_rows.append([key, val.get("Score", ""), val.get("Assessment", "")])
        table = Table(data_rows, colWidths=[1.5 * inch, 1.2 * inch, 3.3 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Competitive Landscape Table
    comp = scorecard.get("CompetitiveLandscape", [])
    if comp:
        elements.append(Paragraph("Competitive Landscape", styles['Heading2']))
        data_rows = [["Name", "USP", "Business Model Alignment"]]
        for c in comp:
            data_rows.append([c.get("Name", ""), c.get("USP", ""), c.get("BusinessModelAlignment", "")])
        table = Table(data_rows, colWidths=[1.5 * inch, 2.5 * inch, 2.0 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Uncertainty Analysis Table
    ua = scorecard.get("UncertaintyAnalysis", [])
    if ua:
        elements.append(Paragraph("Uncertainty Analysis", styles['Heading2']))
        data_rows = [["Category", "Risk Score", "Rationale"]]
        for u in ua:
            data_rows.append([u.get("Category", ""), u.get("RiskScore", ""), u.get("Rationale", "")])
        table = Table(data_rows, colWidths=[1.5 * inch, 1.2 * inch, 3.3 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    add_section("Exit Options", scorecard.get("ExitOptions", []))
    add_section("Comments", scorecard.get("Comments", []))

    doc.build(elements)
    buffer.seek(0)
    return buffer
