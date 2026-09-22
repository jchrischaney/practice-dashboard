import streamlit as st
import pandas as pd
import os
import google.genai as genai
from google.genai import types

# --------------------------------------------------------------------
# 1. INITIALIZE GEMINI API Client
# --------------------------------------------------------------------
# Streamlit Cloud will securely inject your API key here from your Secrets manager
client = genai.Client()

# --------------------------------------------------------------------
# 2. FILE TRACKING & DATA CLEANING ENGINE
# --------------------------------------------------------------------
MASTER_FILE = "master_medical_data.csv"

def clean_and_parse_report(uploaded_file):
    """Parses specific nested, grouped CPT Level CSV report format"""
    # Read raw CSV, skipping metadata headers
    df = pd.read_csv(uploaded_file, skiprows=5)
    df.columns = df.columns.str.strip()
    
    # Filter out empty spacer rows, footers, or sub-totals
    df = df[df['CPT Code'].notna()]
    df = df[df['Appointment / Servicing Provider'] != 'Overall']
    
    # Fix the grouped hierarchy layout by forward-filling blank rows
    df['Appointment / Servicing Provider'] = df['Appointment / Servicing Provider'].ffill()
    df['Facility'] = df['Facility'].ffill()
    
    # Clean and convert string numbers to real financial numbers
    financial_cols = ['Billed Charge', 'Payer Charge', 'Self Charge', 'Payment', 
                      'Contractual Adjustment', 'Patient Count', 'Claim Count', 'Units', 'Change in A/R']
    for col in financial_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            
    # Add a column to mark when this data was added
    df['Upload Month'] = pd.Timestamp.now().strftime('%B %Y')
    return df

# Load the historical master dataset if it exists
if os.path.exists(MASTER_FILE):
    master_df = pd.read_csv(MASTER_FILE)
else:
    master_df = pd.DataFrame()

# --------------------------------------------------------------------
# 3. STREAMLIT USER INTERFACE DESIGN
# --------------------------------------------------------------------
st.set_page_config(page_title="Practice Metrics Dashboard", layout="wide")
st.title("🩺 Medical Practice Analytics & AI Copilot")
st.subheader("May-July 2026 Financial & Productivity Monitoring")

# Sidebar for File Uploads
with st.sidebar:
    st.header("📥 Data Management")
    uploaded_file = st.file_uploader("Upload Monthly CPT Analysis Report (CSV)", type=["csv"])
    
    if uploaded_file is not None:
        if st.button("Process & Append to Master"):
            new_data = clean_and_parse_report(uploaded_file)
            
            if master_df.empty:
                master_df = new_data
            else:
                # Merge new rows into our master tracking file
                master_df = pd.concat([master_df, new_data], ignore_index=True)
                
            master_df.to_csv(MASTER_FILE, index=False)
            st.success(f"Successfully processed and updated master database!")
            st.rerun()
            
    if not master_df.empty:
        st.info(f"📁 Current Database Size: {len(master_df)} records across tracked months.")
        if st.button("Clear Master Database"):
            if os.path.exists(MASTER_FILE):
                os.remove(MASTER_FILE)
            st.warning("Database cleared.")
            st.rerun()

# Stop application execution if there is no data to visualize yet
if master_df.empty:
    st.info("Welcome! Please upload an initial spreadsheet in the sidebar to populate your dashboard metrics.")
    st.stop()

# --------------------------------------------------------------------
# 4. DATA VISUALIZATION DASHBOARD
# --------------------------------------------------------------------
# Top Level KPIs
total_billed = master_df['Billed Charge'].sum()
total_paid = master_df['Payment'].sum()
collection_rate = (total_paid / total_billed * 100) if total_billed > 0 else 0

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Gross Billed Charges", f"${total_billed:,.2f}")
kpi2.metric("Total Reimbursements Received", f"${total_paid:,.2f}")
kpi3.metric("Gross Collection Rate", f"{collection_rate:.1f}%")

st.divider()

# Charts: Provider Metrics Breakdown
st.subheader("👨‍⚕️ Provider Performance & CPT Metrics")
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("**Total Payments vs. Billed Charges by Provider**")
    provider_data = master_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum()
    st.bar_chart(provider_data)

with chart_col2:
    st.markdown("**Top 10 CPT Codes by Transaction Volume (Units)**")
    cpt_data = master_df.groupby('CPT Code')['Units'].sum().sort_values(ascending=False).head(10)
    st.bar_chart(cpt_data)

st.divider()

# --------------------------------------------------------------------
# 5. AI ENGINE: LIVE INSIGHTS & CUSTOM CHAT QUERIES
# --------------------------------------------------------------------
st.subheader("🤖 Gemini Financial Copilot")

tab1, tab2 = st.tabs(["📋 Monthly Executive Summary", "💬 Chat / Query Data"])

# Context setup to feed aggregated data directly to Gemini efficiently
data_summary_for_ai = master_df.groupby(['Appointment / Servicing Provider', 'CPT Code'])[['Billed Charge', 'Payment', 'Units']].sum().reset_index().to_string(index=False)

with tab1:
    if st.button("Generate Monthly Executive Briefing"):
        with st.spinner("Gemini is auditing your practice data for revenue insights..."):
            prompt = f"""
            You are a healthcare financial analyst. Analyze this medical practice financial summary aggregated by provider and CPT code:
            {data_summary_for_ai}
            
            Provide a 3-part Executive Briefing:
            1. **Financial Overview**: Highlight top producing providers and key collection bottlenecks.
            2. **CPT Coding Shifts**: Spot anomalies where high-complexity codes or medications (like J-codes) show poor reimbursement ratios.
            3. **Actionable Leak Detection**: Point out where the practice is leaving money on the table (high adjustments or low collections).
            Keep it strictly professional and highly concise using bullet points.
            """
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-pro',
                    contents=prompt,
                )
                st.markdown(response.text)
            except Exception as e:
                st.error(f"API Connection Error: {e}")

with tab2:
    st.write("Ask Gemini specific questions about your financial rows (e.g., 'Who billed the most for critical care code 99291?' or 'What is Dr. Yuhico's collection rate on J-codes?')")
    user_query = st.text_input("Enter your natural language data question:")
    
    if user_query:
        with st.spinner("Analyzing data table..."):
            chat_prompt = f"""
            You are an interactive business intelligence assistant for a medical group. 
            You are looking at this parsed operational dataset:
            {data_summary_for_ai}
            
            Answer the user's specific question clearly, citing values from the data above where appropriate.
            User Question: {user_query}
            """
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=chat_prompt,
                )
                st.write(response.text)
            except Exception as e:
                st.error(f"Error answering your query: {e}")
