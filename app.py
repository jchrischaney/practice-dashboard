import streamlit as st
import pandas as pd
import os
import google.genai as genai
from google.genai import types

# --------------------------------------------------------------------
# 1. INITIALIZE GEMINI API Client
# --------------------------------------------------------------------
client = genai.Client()

# --------------------------------------------------------------------
# 2. FILE TRACKING & DATA CLEANING ENGINE
# --------------------------------------------------------------------
MASTER_FILE = "master_medical_data.csv"

def clean_and_parse_report(uploaded_file):
    """Parses specific nested, grouped CPT Level CSV report format perfectly"""
    df = pd.read_csv(uploaded_file, skiprows=5)
    df.columns = df.columns.str.strip()
    
    df = df[df['CPT Code'].notna()]
    df = df[df['Appointment / Servicing Provider'] != 'Overall']
    
    df['Appointment / Servicing Provider'] = df['Appointment / Servicing Provider'].ffill()
    df['Facility'] = df['Facility'].ffill()
    
    # Standardize CPT code column to strings without hidden spaces
    df['CPT Code'] = df['CPT Code'].astype(str).str.strip()
    
    financial_cols = ['Billed Charge', 'Payer Charge', 'Self Charge', 'Payment', 
                      'Contractual Adjustment', 'Patient Count', 'Claim Count', 'Units', 'Change in A/R']
    for col in financial_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('$', '', regex=False)
            df[col] = df[col].str.replace(',', '', regex=False)
            df[col] = df[col].str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    df['Upload Month'] = pd.Timestamp.now().strftime('%B %Y')
    return df

if os.path.exists(MASTER_FILE):
    master_df = pd.read_csv(MASTER_FILE)
    # Ensure CPT code is read as string consistently
    master_df['CPT Code'] = master_df['CPT Code'].astype(str).str.strip()
    financial_cols = ['Billed Charge', 'Payer Charge', 'Self Charge', 'Payment', 
                      'Contractual Adjustment', 'Patient Count', 'Claim Count', 'Units', 'Change in A/R']
    for col in financial_cols:
        if col in master_df.columns:
            master_df[col] = pd.to_numeric(master_df[col], errors='coerce').fillna(0)
else:
    master_df = pd.DataFrame()

# --------------------------------------------------------------------
# 3. STREAMLIT USER INTERFACE DESIGN
# --------------------------------------------------------------------
st.set_page_config(page_title="American Medical Group Practice Analytics", layout="wide")
st.title("🩺 American Medical Group Practice Analytics")
st.subheader("Executive Financial & Productivity Copilot")

with st.sidebar:
    st.header("📥 Data Management")
    uploaded_file = st.file_uploader("Upload Monthly CPT Analysis Report (CSV)", type=["csv"])
    
    if uploaded_file is not None:
        if st.button("Process & Append to Master"):
            new_data = clean_and_parse_report(uploaded_file)
            if master_df.empty:
                master_df = new_data
            else:
                master_df = pd.concat([master_df, new_data], ignore_index=True)
            master_df.to_csv(MASTER_FILE, index=False)
            st.success("Successfully processed and updated master database!")
            st.rerun()
            
    if not master_df.empty:
        st.info(f"📁 Current Database Size: {len(master_df)} records across tracked months.")
        if st.button("Clear Master Database"):
            if os.path.exists(MASTER_FILE):
                os.remove(MASTER_FILE)
            st.warning("Database cleared.")
            st.rerun()
            
    st.divider()
    
    with st.expander("📋 CPT Code Quick-Reference Cheat Sheet", expanded=False):
        st.markdown("**E&M - CRITICAL CARE**")
        st.markdown("* **99291** : Critical Care (First 30–74 min)\n* **99292** : Critical Care (Each additional 30 min)")
        st.markdown("**E&M - INPATIENT HOSPITAL**")
        st.markdown("* **99222** : Initial Inpatient (Moderate Severity)\n* **99223** : Initial Inpatient (High Severity)\n* **99232** : Subsequent Inpatient (Stable)\n* **99233** : Subsequent Inpatient (Unstable)")
        st.markdown("**E&M - OFFICE / OUTPATIENT**")
        st.markdown("* **99202-99205** : New Patient Clinic Visits\n* **99212-99215** : Established Patient Clinic Visits")
        st.markdown("**PULMONARY FUNCTION TESTING (PFT)**")
        st.markdown("* **94010-94799** : Complete Lung Volume & Diagnostic PFT Panel")

if master_df.empty:
    st.info("Welcome! Please upload an initial spreadsheet in the sidebar to populate your dashboard metrics.")
    st.stop()

# --------------------------------------------------------------------
# 4. DATA VISUALIZATION DASHBOARD (SEGREGATED SECTIONS)
# --------------------------------------------------------------------
# Global Practice KPIs
total_billed = float(master_df['Billed Charge'].sum())
total_paid = float(master_df['Payment'].sum())
collection_rate = (total_paid / total_billed * 100) if total_billed > 0 else 0

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Gross Billed Charges", f"${total_billed:,.2f}")
kpi2.metric("Total Reimbursements Received", f"${total_paid:,.2f}")
kpi3.metric("Gross Collection Rate", f"{collection_rate:.1f}%")

st.divider()

# --- SECTION A: INPATIENT VS OUTPATIENT SEGREGATION ---
st.subheader("🏢 Core Service Line Splits (Inpatient vs. Outpatient Clinic)")
line_col1, line_col2 = st.columns(2)

# Defined Outpatient Codes List
outpatient_codes = ['99202', '99203', '99204', '99205', '99212', '99213', '99214', '99215']

with line_col1:
    st.markdown("**🏥 Outpatient Clinic Numbers by Provider**")
    outpatient_df = master_df[master_df['CPT Code'].isin(outpatient_codes)]
    if not outpatient_df.empty:
        outpatient_provider = outpatient_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum()
        st.bar_chart(outpatient_provider)
    else:
        st.caption("No matching Outpatient E&M data found.")

with line_col2:
    st.markdown("**🏥 Inpatient Hospital & Critical Care Numbers by Provider**")
    # Inpatient is defined as rows that are NOT outpatient codes, NOT J-codes, and NOT PFT codes
    inpatient_df = master_df[
        (~master_df['CPT Code'].isin(outpatient_codes)) & 
        (~master_df['CPT Code'].str.startswith('J', na=False)) & 
        (~master_df['CPT Code'].str.startswith('Q', na=False))
    ]
    # Filter numeric PFT ranges out of inpatient mapping
    inpatient_df = inpatient_df[~inpatient_df['CPT Code'].str.match(r'^94[0-7]\d\d', na=False)]
    
    if not inpatient_df.empty:
        inpatient_provider = inpatient_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum()
        st.bar_chart(inpatient_provider)
    else:
        st.caption("No matching Inpatient/Critical Care data found.")

st.divider()

# --- SECTION B: MEDICATION INFUSIONS & PFT LABS ---
st.subheader("🔬 Specialized Service Lines (IV Infusions & PFT Lab Tracking)")
spec_col1, spec_col2 = st.columns(2)

with spec_col1:
    st.markdown("**🧪 IV Infusions & Biologics (J-Codes) by Provider**")
    # Filters rows where CPT starts with J
    j_code_df = master_df[master_df['CPT Code'].str.startswith('J', na=False)]
    if not j_code_df.empty:
        j_provider = j_code_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum()
        st.bar_chart(j_provider)
    else:
        st.caption("No Medication Infusion (J-Code) transactions found.")

with spec_col2:
    st.markdown("**🫁 Pulmonary Function Testing (PFT 94010–94799) by Provider**")
    # Filters rows where CPT Code is numerically inside the standard 94010-94799 PFT range
    master_df['CPT_Numeric'] = pd.to_numeric(master_df['CPT Code'], errors='coerce')
    pft_df = master_df[(master_df['CPT_Numeric'] >= 94010) & (master_df['CPT_Numeric'] <= 94799)]
    
    if not pft_df.empty:
        pft_provider = pft_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum()
        st.bar_chart(pft_provider)
    else:
        st.caption("No Pulmonary Function Test (PFT) data transactions found.")

st.divider()

# --------------------------------------------------------------------
# 5. AI ENGINE: LIVE INSIGHTS & CUSTOM CHAT QUERIES
# --------------------------------------------------------------------
st.subheader("🤖 Gemini Financial Copilot")
tab1, tab2 = st.tabs(["📋 Segregated Executive Summary", "💬 Chat / Query Data"])

# Create safe matrices summaries to feed to the AI context seamlessly
prov_summary = master_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum().reset_index().to_string(index=False)
outpatient_summary = outpatient_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum().reset_index().to_string(index=False) if not outpatient_df.empty else "No Outpatient Data"
jcode_summary = j_code_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum().reset_index().to_string(index=False) if not j_code_df.empty else "No J-Code Data"
pft_summary = pft_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum().reset_index().to_string(index=False) if not pft_df.empty else "No PFT Data"

with tab1:
    if st.button("Generate Segmented Executive Briefing"):
        with st.spinner("Gemini is auditing your specialized service lines..."):
            ai_prompt = f"""You are an expert healthcare financial analyst. Analyze this multi-segment performance breakdown for a Pulmonary practice:

GLOBAL PROVIDER TOTALS:
{prov_summary}

OUTPATIENT CLINIC VISITS EXCLUSIVELY:
{outpatient_summary}

MEDICATION INFUSIONS (J-CODES):
{jcode_summary}

PULMONARY FUNCTION TESTING (PFT LAB):
{pft_summary}

Provide a crisp 3-part Executive Briefing:
1. **Clinic vs Inpatient Footprint**: Compare who dominates outpatient clinics vs inpatient hospital revenue.
