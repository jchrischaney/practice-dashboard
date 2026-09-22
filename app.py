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
    # Read raw CSV, skipping metadata headers
    df = pd.read_csv(uploaded_file, skiprows=5)
    df.columns = df.columns.str.strip()
    
    # Filter out empty spacer rows, footers, or sub-totals
    df = df[df['CPT Code'].notna()]
    df = df[df['Appointment / Servicing Provider'] != 'Overall']
    
    # Fix the grouped hierarchy layout by forward-filling blank rows
    df['Appointment / Servicing Provider'] = df['Appointment / Servicing Provider'].ffill()
    df['Facility'] = df['Facility'].ffill()
    
    # Clean and convert string numbers to real financial numbers aggressively
    financial_cols = ['Billed Charge', 'Payer Charge', 'Self Charge', 'Payment', 
                      'Contractual Adjustment', 'Patient Count', 'Claim Count', 'Units', 'Change in A/R']
    for col in financial_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('$', '', regex=False)
            df[col] = df[col].str.replace(',', '', regex=False)
            df[col] = df[col].str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    # Add a column to mark when this data was added
    df['Upload Month'] = pd.Timestamp.now().strftime('%B %Y')
    return df

# Load the historical master dataset if it exists
if os.path.exists(MASTER_FILE):
    master_df = pd.read_csv(MASTER_FILE)
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
st.set_page_config(page_title="Practice Metrics Dashboard", layout="wide")
st.title("🩺 Medical Practice Analytics & AI Copilot")
st.subheader("May-July 2026 Financial & Productivity Monitoring")

# Sidebar for File Uploads & CPT Code Cheat Sheet
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
            st.success(f"Successfully processed and updated master database!")
            st.rerun()
            
    if not master_df.empty:
        st.info(f"📁 Current Database Size: {len(master_df)} records across tracked months.")
        if st.button("Clear Master Database"):
            if os.path.exists(MASTER_FILE):
                os.remove(MASTER_FILE)
            st.warning("Database cleared.")
            st.rerun()
            
    st.divider()
    
    # ----------------------------------------------------------------
    # NEW INTERACTIVE COLLAPSIBLE CHEAT SHEET SECTION
    # ----------------------------------------------------------------
    with st.expander("📋 CPT Code Quick-Reference Cheat Sheet", expanded=False):
        st.markdown("""
        **E&M - CRITICAL CARE**
        * **99291** : Critical Care (First 30–74 min)
        * **99292** : Critical Care (Each additional 30 min)
        
        **E&M - INPATIENT HOSPITAL**
        * **99222** : Initial Inpatient (Moderate Severity)
        * **99223** : Initial Inpatient (High Severity)
        * **99232** : Subsequent Inpatient (Stable / Evolving)
        * **99233** : Subsequent Inpatient (Unstable / Significant)
        * **99254** : Inpatient Hospital Consultation
        
        **E&M - OFFICE / OUTPATIENT**
        * **99203** : New Patient Visit (Moderate / 30-44 min)
        * **99204** : New Patient Visit (High / 45-59 min)
        * **99205** : New Patient Visit (Extensive / 60-74 min)
        * **99212** : Established Patient (Straightforward / 10-19 min)
        * **99213** : Established Patient (Low Complexity / 20-29 min)
        * **99214** : Established Patient (Moderate Complexity / 30-39 min)
        * **99215** : Established Patient (High Complexity / 40-54 min)
        * **99496** : Transitional Care Management (Within 7 Days)
        
        **EMERGENCY & CRITICAL CARE ACCESS**
        * **31500** : Emergency Endotracheal Intubation
        * **92950** : Cardiopulmonary Resuscitation (CPR)
        * **36556** : Central Venous Line Placement (Age 5+)
        * **36620** : Arterial Line Insertion (BP Monitoring)
        * **76937** : Ultrasound Guidance for Vascular Access
        
        **PULMONARY & BRONCHOSCOPY**
        * **31623** : Bronchoscopy with Brushings
        * **31624** : Bronchoscopy with Lavage (BAL)
        * **31627** : Bronchoscopy with Computer Navigation
        * **31628** : Bronchoscopy with Transbronchial Lung Biopsy
        * **31629** : Bronchoscopy with Transbronchial Needle Biopsy
        * **31635** : Bronchoscopy with Foreign Body Removal
        * **31641** : Bronchoscopy with Tumor/Lesion Destruction
        * **31645** : Bronchoscopy with Therapeutic Airway Aspiration
        * **31653** : Bronchoscopy with EBUS Biopsy (1-2 Nodes)
        * **31654** : Bronchoscopy with EBUS Biopsy (Additional Nodes)
        
        **MEDICATION INFUSIONS (J-CODES)**
        * **96365** : Intravenous Infusion Therapy (First Hour)
        * **96367** : Intravenous Infusion Therapy (Sequential Hour)
        * **J0121** : Injection, Tigecycline Antibiotic (per 1 mg)
        * **J0256** : Injection, Alpha 1-Proteinase Inhibitor (per 10 mg)
        * **J0696** : Injection, Ceftriaxone Sodium Rocephin (per 250 mg)
        * **J1335** : Injection, Ertapenem Sodium Invanz (per 500 mg)
        * **J1561** : Injection, Immune Globulin Intravenous (per 500 mg)
        * **J2919** : Injection, Solu-Medrol (per 40 mg)
        * **Q0224** : Injection, Evusheld COVID Therapeutic
        
        **PULMONARY FUNCTION TESTING (PFT)**
        * **94010** : Spirometry (Graphic record / timed volume)
        * **94060** : Bronchospasm Evaluation (Pre/Post Spirometry)
        * **94618** : Pulmonary Stress Testing (Hypoxia simulation)
        * **94726** : Plethysmography (Lung volume/airway resistance)
        * **94729** : Diffusing Capacity (Carbon monoxide testing)
        * **95800** : Sleep Study (Home monitoring)
        """)

# Stop application execution if there is no data to visualize yet
if master_df.empty:
    st.info("Welcome! Please upload an initial spreadsheet in the sidebar to populate your dashboard metrics.")
    st.stop()

# --------------------------------------------------------------------
# 4. DATA VISUALIZATION DASHBOARD
# --------------------------------------------------------------------
total_billed = float(master_df['Billed Charge'].sum())
total_paid = float(master_df['Payment'].sum())
collection_rate = (total_paid / total_billed * 100) if total_billed > 0 else 0

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Gross Billed Charges", f"${total_billed:,.2f}")
kpi2.metric("Total Reimbursements Received", f"${total_paid:,.2f}")
kpi3.metric("Gross Collection Rate", f"{collection_rate:.1f}%")

st.divider()

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
