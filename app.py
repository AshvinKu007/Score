import streamlit as st
from utils import extract_pdf_text, analyze_pitch_deck, generate_scorecard_pdf

st.set_page_config(page_title="Startup Scorecard Generator", layout="wide")
st.title("📊 Startup Scorecard Generator")
st.markdown("Upload a pitch deck PDF and get an investment scorecard generated using Gemini Pro.")

api_key = st.text_input("🔑 Enter Gemini API Key", type="password")
uploaded_file = st.file_uploader("📤 Upload Pitch Deck (PDF)", type=["pdf"])

if uploaded_file and api_key:
    with st.spinner("Extracting content and analyzing..."):
        text = extract_pdf_text(uploaded_file)
        if not text.strip():
            st.error("❌ No extractable text found in the PDF.")
        else:
            result, raw_response = analyze_pitch_deck(text, api_key, return_raw=True)
            if result:
                pdf_bytes = generate_scorecard_pdf(result)
                st.success("✅ Scorecard generated successfully!")
                st.download_button(
                    label="📥 Download Scorecard PDF",
                    data=pdf_bytes.getvalue(),
                    file_name=f"Scorecard_{result['StartupName'].replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )
            else:
                st.error("❌ Failed to generate scorecard. Please try again or check the Gemini API key.")
                with st.expander("Show Gemini raw response for debugging"):
                    st.write(raw_response or "No response.")
else:
    st.info("Please upload a PDF and enter your Gemini API key to begin.")
