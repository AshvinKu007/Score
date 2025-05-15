import streamlit as st
from utils import extract_pdf_text, analyze_pitch_deck, generate_scorecard_pdf
from io import BytesIO
import zipfile

st.set_page_config(page_title="Startup Scorecard Generator", layout="wide")
st.title("📊 Startup Scorecard Generator")
st.markdown("Upload one or more pitch deck PDFs and get investment scorecards generated using Gemini Pro.")

api_key = st.text_input("🔑 Enter Gemini API Key", type="password")
uploaded_files = st.file_uploader("📤 Upload Pitch Deck PDFs", type=["pdf"], accept_multiple_files=True)

if uploaded_files and api_key:
    pdf_buffers = []
    error_files = []
    with st.spinner("Extracting content and analyzing..."):
        for uploaded_file in uploaded_files:
            text = extract_pdf_text(uploaded_file)
            if not text.strip():
                error_files.append(uploaded_file.name)
                continue
            result, raw_response = analyze_pitch_deck(text, api_key, return_raw=True)
            if result:
                pdf_buffer = generate_scorecard_pdf(result)
                pdf_name = f"Scorecard_{result['StartupName'].replace(' ', '_')}.pdf"
                pdf_buffers.append((pdf_name, pdf_buffer))
            else:
                error_files.append(uploaded_file.name)
    if pdf_buffers:
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            for pdf_name, pdf_buffer in pdf_buffers:
                zip_file.writestr(pdf_name, pdf_buffer.getvalue())
        zip_buffer.seek(0)
        st.success(f"✅ Generated {len(pdf_buffers)} scorecard(s).")
        st.download_button(
            label="📥 Download All Scorecards as ZIP",
            data=zip_buffer,
            file_name="scorecards.zip",
            mime="application/zip"
        )
    if error_files:
        st.error(f"Failed to process: {', '.join(error_files)}")
elif uploaded_files and not api_key:
    st.warning("Please enter your Gemini API key.")
else:
    st.info("Please upload one or more PDFs and enter your Gemini API key to begin.")
