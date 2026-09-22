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
        st.markdown("* **99222** : Initial Inpatient (Moderate Severity)\n* **99223** : Initial Inpatient (High Severity)\n* **99232** : Subsequent Inpatient (Stable)\n* **99233** : Subsequent Inpatient (Unstable)\n* **99254** : Inpatient Hospital Consultation")
        
        st.markdown("**E&M - OFFICE / OUTPATIENT**")
        st.markdown("* **99203** : New Patient (Moderate / 30-44 min)\n* **99204** : New Patient (High / 45-59 min)\n* **99205** : New Patient (Extensive / 60-74 min)\n* **99212** : Established Patient (10-19 min)\n* **99213** : Established Patient (Low / 20-29 min)\n* **99214** : Established Patient (Moderate / 30-39 min)\n* **99215** : Established Patient (High / 40-54 min)\n* **99496** : Transitional Care (Within 7 Days)")
        
        st.markdown("**EMERGENCY & CRITICAL CARE ACCESS**")
        st.markdown("* **31500** : Emergency Endotracheal Intubation\n* **92950** : Cardiopulmonary Resuscitation (CPR)\n* **36556** : Central Venous Line Placement\n* **36620** : Arterial Line Insertion\n* **76937** : Ultrasound Guidance for Vascular Access")
        
        st.markdown("**PULMONARY & BRONCHOSCOPY**")
        st.markdown("* **31623** : Bronchoscopy with Brushings\n* **31624** : Bronchoscopy with Lavage (BAL)\n* **31627** : Bronchoscopy with Computer Navigation\n* **31628** : Bronchoscopy with Lung Biopsy\n* **31629** : Bronchoscopy with Needle Biopsy\n* **31635** : Bronchoscopy with Foreign Body Removal\n* **31641** : Bronchoscopy with Tumor Destruction\n* **31645** : Bronchoscopy with Airway Aspiration\n* **31653** : Bronchoscopy with EBUS Biopsy (1-2 Nodes)\n* **31654** : Bronchoscopy with EBUS Biopsy (Additional Nodes)")
        
        st.markdown("**MEDICATION INFUSIONS (J-CODES)**")
        st.markdown("* **96365** : IV Infusion Therapy (First Hour)\n* **96367** : IV Infusion Therapy (Sequential Hour)\n* **J0121** : Injection, Tigecycline Antibiotic (1 mg)\n* **J0256** : Injection, Alpha 1-Proteinase (10 mg)\n* **J0696** : Injection, Ceftriaxone Sodium Rocephin\n* **J1335** : Injection, Ertapenem Sodium Invanz\n* **J1561** : Injection, Immune Globulin IV\n* **J2919** : Injection, Solu-Medrol (40 mg)\n* **Q0224** : Injection, Evusheld COVID Therapeutic")
        
        st.markdown("**PULMONARY FUNCTION TESTING (PFT)**")
        st.markdown("* **94010** : Spirometry (Graphic record)\n* **94060** : Bronchospasm Evaluation (Pre/Post)\n* **94618** : Pulmonary Stress Testing\n* **94726** : Plethysmography (Lung volume)\n* **94729** : Diffusing Capacity (Carbon monoxide)\n* **95800** : Sleep Study (Home monitoring)")

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
            prompt = f"You are a healthcare financial analyst. Analyze this medical practice financial summary aggregated by provider and CPT code:\n{data_summary_for_ai}\n\nProvide a 3-part Executive Briefing:\n1. **Financial Overview**: Highlight top producing providers and key collection bottlenecks.\n2. **CPT Coding Shifts**: Spot anomalies where high-complexity codes or medications (like J-codes) show poor reimbursement ratios.\n3. **Actionable Leak Detection**: Point out where the practice is leaving money on the table (high adjustments or low collections)."
            # ROUTED TO ACTIVE PRODUCTION RUNTIME MODEL
            response = client.models.generate_content(model='gemini-3.5-flash', contents=prompt)
            st.markdown(response.text)

with tab2:
    st.write("Ask Gemini specific questions about your financial rows (e.g., 'Who billed the most for critical care code 99291?' or 'What is Dr. Yuhico's collection rate on J-codes?')")
    user_query = st.text_input("Enter your natural language data question:")
    
    if user_query:
        with st.spinner("Analyzing data table..."):
            chat_prompt = f"You are an interactive business intelligence assistant for a medical group. You are looking at this parsed operational dataset:\n{data_summary_for_ai}\n\nAnswer the user's specific question clearly, citing values from the data above where appropriate.\nUser Question: {user_query}"
            # ROUTED TO ACTIVE PRODUCTION RUNTIME MODEL
            response = client.models.generate_content(model='gemini-3.5-flash', contents=chat_prompt)
            st.write(response.text)
