import fitz  # PyMuPDF
import json5
import re
import time
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
    safe_pitch_text = pitch_text[:28000].replace("```", "")
    prompt = f"""
Generate VALID JSON for an investment scorecard using this structure:
{{
  "StartupName": "string",
  "OverallScore": null,
  "ExecutiveSummary": ["string"],
  "Sector": "string",
  "SectorAnalysisIndia": ["string"],
  "TracxnStyleBenchmark": {{
    "Stage": "Early/Growth/Late",
    "ProductType": "Platform/SaaS/etc.",
    "Tag": "e.g. B2B Payments",
    "RecentActivity": "string"
  }},
  "CompetitiveLandscape": [
    {{
      "Name": "string",
      "USP": "string",
      "BusinessModelAlignment": "string"
    }}
  ],
  "ProductMarketFit": {{
    "ProofOfConcept": [0-100, "string"],
    "MarketDisruption": [0-100, "string"],
    "CostToOperation": [0-100, "string"],
    "QualityInIncumbents": [0-100, "string"],
    "SpeedToIncumbents": [0-100, "string"],
    "RealProblem": [0-100, "string"]
  }},
  "GTMExecution": {{
    "CostOfAcquisition": [0-100, "string"],
    "CustomerStickiness": [0-100, "string"],
    "Pricing": [0-100, "string"]
  }},
  "SupplyChainOps": {{
    "AmpleSupplyTargetCost": [0-100, "string"],
    "ManagingBusinessComplexity": [0-100, "string"],
    "AbilityToReaccelerate": [0-100, "string"]
  }},
  "BusinessModel": {{
    "UnitEconomics": [0-100, "string"],
    "LongTermSustainability": [0-100, "string"],
    "FundingInSight": [0-100, "string"]
  }},
  "FoundersEvaluation": {{
    "Vision": [0-100, "string"],
    "Leadership": [0-100, "string"],
    "BusinessAcumen": [0-100, "string"],
    "Execution": [0-100, "string"],
    "Resilience": [0-100, "string"]
  }},
  "ExitOptions": ["string"],
  "Comments": ["string"],
  "UncertaintyAnalysis": {{
    "Market": {{"Score": 0-100, "Rationale": ["string"]}},
    "Technology": {{"Score": 0-100, "Rationale": ["string"]}},
    "TeamExecution": {{"Score": 0-100, "Rationale": ["string"]}},
    "Financial": {{"Score": 0-100, "Rationale": ["string"]}},
    "Legal": {{"Score": 0-100, "Rationale": ["string"]}}
  }}
}}
For CompetitiveLandscape, identify top 3 relevant competitors using AI and sector knowledge (not from pitch deck).
Use only double quotes. Return ONLY valid JSON.
PITCH DECK:
<<PITCH>>
""".replace("<<PITCH>>", safe_pitch_text[:28000].replace('"', "'"))

    model = genai.GenerativeModel("gemini-1.5-pro-latest", generation_config={
        "temperature": 0,
        "response_mime_type": "application/json",
        "max_output_tokens": 4000
    })

    raw = None  # Initialize raw to avoid UnboundLocalError
    for attempt in range(5):
        try:
            response = model.generate_content(prompt)
            raw = response.text.strip().replace("``````", "")
            # Fix for mismatched braces/brackets
            open_braces = raw.count("{")
            close_braces = raw.count("}")
            if open_braces > close_braces:
                raw += "}" * (open_braces - close_braces)
            open_brackets = raw.count("[")
            close_brackets = raw.count("]")
            if open_brackets > close_brackets:
                raw += "]" * (open_brackets - close_brackets)
            data = json5.loads(raw)
            if data and validate_structure(data):
                return (data, raw) if return_raw else data
        except Exception as e:
    print(f"⚠️ Attempt {attempt+1} failed: {e}")
    print(f"Gemini raw output:\n{raw[:1000]}...\n")  # Add this
    time.sleep(2 ** attempt)
    continue

    return (None, raw) if return_raw else None

def compute_overall_score(scorecard):
    def avg_section(section):
        vals = []
        for v in section.values():
            if isinstance(v, (list, tuple)) and len(v) > 0 and isinstance(v[0], (int, float)):
                vals.append(float(v[0]))
        return sum(vals) / len(vals) if vals else 0

    pmf = avg_section(scorecard.get("ProductMarketFit", {}))
    gtm = avg_section(scorecard.get("GTMExecution", {}))
    sc  = avg_section(scorecard.get("SupplyChainOps", {}))
    bm  = avg_section(scorecard.get("BusinessModel", {}))
    fe  = avg_section(scorecard.get("FoundersEvaluation", {}))
    overall = round((pmf + gtm + sc + bm + fe) / 5, 2)
    return overall

if data and validate_structure(data):
    data["OverallScore"] = compute_overall_score(data)
    return (data, raw) if return_raw else data

   

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
        if isinstance(content, list):
            for item in content:
                elements.append(Paragraph(f"- {item}", styles['Normal']))
        else:
            elements.append(Paragraph(str(content), styles['Normal']))
        elements.append(Spacer(1, 12))

    def add_matrix(title, section):
        elements.append(Paragraph(title, styles['Heading2']))
        data_rows = [["Parameter", "Score (/100)", "Reason"]]
        for key, val in section.items():
            label = re.sub(r"(?<!^)(?=[A-Z])", " ", key)
            if isinstance(val, (list, tuple)) and len(val) == 2:
                score, reason = val
            else:
                score, reason = "-", "-"
            data_rows.append([
                label,
                str(score),
                Paragraph(str(reason), styles['Normal'])
            ])
        table = Table(data_rows, colWidths=[2.2*inch, 0.8*inch, 3.0*inch], repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    def add_founders(section):
        elements.append(Paragraph("Founders Evaluation (/100)", styles['Heading2']))
        data_rows = [["Criteria", "Score", "Assessment"]]
        for key, val in section.items():
            label = re.sub(r"(?<!^)(?=[A-Z])", " ", key)
            if isinstance(val, (list, tuple)) and len(val) == 2:
                score, assessment = val
            else:
                score, assessment = "-", str(val)
            data_rows.append([label, str(score), Paragraph(assessment, styles['Normal'])])
        table = Table(data_rows, colWidths=[2.2*inch, 0.8*inch, 3.0*inch], repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('VALIGN', (0,0), (-1, -1), 'TOP'),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    def add_competitor_table(comp_list):
        elements.append(Paragraph("Competitive Landscape", styles['Heading2']))
        table_data = [["Name", "USP", "Business Model Alignment"]]
        for comp in comp_list:
            table_data.append([
                Paragraph(str(comp.get("Name", "-")), styles['Normal']),
                Paragraph(str(comp.get("USP", "-")), styles['Normal']),
                Paragraph(str(comp.get("BusinessModelAlignment", "-")), styles['Normal'])
            ])
        table = Table(table_data, colWidths=[2.0*inch, 2.5*inch, 2.5*inch], repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'TOP')
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    def add_uncertainty_analysis(uncertainty):
        elements.append(Paragraph("Uncertainty Assessment", styles['Heading2']))
        table_data = [["Category", "Risk Score (0-100)", "Key Rationale"]]
        for key in ["Market", "Technology", "TeamExecution", "Financial", "Legal"]:
            section = uncertainty.get(key, {})
            table_data.append([
                Paragraph(key, styles['Normal']),
                Paragraph(str(section.get("Score", "-")), styles['Normal']),
                Paragraph("<br/>".join(f"- {r}" for r in section.get("Rationale", [])), styles['Normal'])
            ])
        table = Table(table_data, colWidths=[1.5*inch, 1.2*inch, 3.3*inch], repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'TOP')
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Add sections and matrices
    add_section("Executive Summary", scorecard.get("ExecutiveSummary", []))
    add_section("Sector", scorecard.get("Sector", "N/A"))
    add_section("Sector Analysis (India)", scorecard.get("SectorAnalysisIndia", []))
    benchmark = scorecard.get("TracxnStyleBenchmark", {})
    if benchmark:
        elements.append(Paragraph("Tracxn-style Benchmark", styles['Heading2']))
        for k, v in benchmark.items():
            elements.append(Paragraph(f"{k}: {v}", styles['Normal']))
        elements.append(Spacer(1, 12))
    if "CompetitiveLandscape" in scorecard:
        add_competitor_table(scorecard["CompetitiveLandscape"])
    add_matrix("Product Market Fit", scorecard.get('ProductMarketFit', {}))
    add_matrix("Go-to-Market Execution", scorecard.get('GTMExecution', {}))
    add_matrix("Supply Chain & Ops", scorecard.get('SupplyChainOps', {}))
    add_matrix("Business Model", scorecard.get('BusinessModel', {}))
    add_founders(scorecard.get('FoundersEvaluation', {}))
    add_uncertainty_analysis(scorecard.get('UncertaintyAnalysis', {}))
    add_section("Exit Options", scorecard.get('ExitOptions', []))
    add_section("Comments", scorecard.get('Comments', []))

    doc.build(elements)
    buffer.seek(0)
    return buffer
