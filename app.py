import streamlit as st
import pandas as pd
import os
import google.genai as genai

# Initialize Gemini API Client
client = genai.Client()
MASTER_FILE = "master_medical_data.csv"

def clean_and_parse_report(uploaded_file):
    df = pd.read_csv(uploaded_file, skiprows=5)
    df.columns = df.columns.str.strip()
    df = df[df['CPT Code'].notna()]
    df = df[df['Appointment / Servicing Provider'] != 'Overall']
    df['Appointment / Servicing Provider'] = df['Appointment / Servicing Provider'].ffill()
    df['Facility'] = df['Facility'].ffill()
    df['CPT Code'] = df['CPT Code'].astype(str).str.strip()
    
    financial_cols = ['Billed Charge', 'Payer Charge', 'Self Charge', 'Payment', 
                      'Contractual Adjustment', 'Patient Count', 'Claim Count', 'Units', 'Change in A/R']
    for col in financial_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    df['Upload Month'] = pd.Timestamp.now().strftime('%B %Y')
    return df

if os.path.exists(MASTER_FILE):
    master_df = pd.read_csv(MASTER_FILE)
    master_df['CPT Code'] = master_df['CPT Code'].astype(str).str.strip()
    financial_cols = ['Billed Charge', 'Payer Charge', 'Self Charge', 'Payment', 
                      'Contractual Adjustment', 'Patient Count', 'Claim Count', 'Units', 'Change in A/R']
    for col in master_df.columns:
        if col in master_df.columns:
            master_df[col] = pd.to_numeric(master_df[col], errors='coerce').fillna(0)
else:
    master_df = pd.DataFrame()

st.set_page_config(page_title="American Medical Group Practice Analytics", layout="wide")
st.title("🩺 American Medical Group Practice Analytics")
st.subheader("Executive Financial & Productivity Copilot")

with st.sidebar:
    st.header("📥 Data Management")
    uploaded_file = st.file_uploader("Upload Monthly CPT Analysis Report (CSV)", type=["csv"])
    if uploaded_file is not None and st.button("Process & Append to Master"):
        new_data = clean_and_parse_report(uploaded_file)
        master_df = new_data if master_df.empty else pd.concat([master_df, new_data], ignore_index=True)
        master_df.to_csv(MASTER_FILE, index=False)
        st.success("Successfully processed database!")
        st.rerun()
    if not master_df.empty and st.button("Clear Master Database"):
        if os.path.exists(MASTER_FILE):
            os.remove(MASTER_FILE)
        st.warning("Database cleared.")
        st.rerun()
    st.divider()
    with st.expander("📋 CPT Code Quick-Reference Cheat Sheet", expanded=False):
        st.markdown("**E&M - CRITICAL CARE**\n* **99291** : Critical Care (30–74 min)\n* **99292** : Critical Care (Addl 30 min)\n\n**E&M - CLINIC VISITS**\n* **99202-99205** : New Patient Clinic\n* **99212-99215** : Established Patient Clinic\n\n**DIAGNOSTICS & PFT LAB**\n* **94010-94799** : Complete Pulmonary Function Panel")

if master_df.empty:
    st.info("Welcome! Please upload an initial spreadsheet in the sidebar to populate your dashboard metrics.")
    st.stop()

total_billed = float(master_df['Billed Charge'].sum())
total_paid = float(master_df['Payment'].sum())
collection_rate = (total_paid / total_billed * 100) if total_billed > 0 else 0

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Gross Billed Charges", f"${total_billed:,.2f}")
kpi2.metric("Total Reimbursements Received", f"${total_paid:,.2f}")
kpi3.metric("Gross Collection Rate", f"{collection_rate:.1f}%")

st.divider()
st.subheader("🏢 Core Service Line Splits (Inpatient vs. Outpatient Clinic)")
line_col1, line_col2 = st.columns(2)
outpatient_codes = ['99202', '99203', '99204', '99205', '99212', '99213', '99214', '99215']

with line_col1:
    st.markdown("**🏥 Outpatient Clinic Numbers by Provider**")
    outpatient_df = master_df[master_df['CPT Code'].isin(outpatient_codes)]
    if not outpatient_df.empty:
        st.bar_chart(outpatient_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum())
    else:
        st.caption("No matching Outpatient data found.")

with line_col2:
    st.markdown("**🏥 Inpatient Hospital & Critical Care Numbers by Provider**")
    inpatient_df = master_df[(~master_df['CPT Code'].isin(outpatient_codes)) & (~master_df['CPT Code'].str.startswith('J', na=False)) & (~master_df['CPT Code'].str.startswith('Q', na=False))]
    inpatient_df = inpatient_df[~inpatient_df['CPT Code'].str.match(r'^94[0-7]\d\d', na=False)]
    if not inpatient_df.empty:
        st.bar_chart(inpatient_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum())
    else:
        st.caption("No matching Inpatient data found.")

st.divider()
st.subheader("🔬 Specialized Service Lines (IV Infusions & PFT Lab Tracking)")
spec_col1, spec_col2 = st.columns(2)

with spec_col1:
    st.markdown("**🧪 IV Infusions & Biologics (J-Codes) by Provider**")
    j_code_df = master_df[master_df['CPT Code'].str.startswith('J', na=False)]
    if not j_code_df.empty:
        st.bar_chart(j_code_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum())
    else:
        st.caption("No Medication Infusion data found.")

with spec_col2:
    st.markdown("**🫁 Pulmonary Function Testing (PFT 94010–94799) by Provider**")
    master_df['CPT_Numeric'] = pd.to_numeric(master_df['CPT Code'], errors='coerce')
    pft_df = master_df[(master_df['CPT_Numeric'] >= 94010) & (master_df['CPT_Numeric'] <= 94799)]
    if not pft_df.empty:
        st.bar_chart(pft_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum())
    else:
        st.caption("No PFT data found.")

st.divider()
st.subheader("🤖 Gemini Financial Copilot")

prov_matrix = master_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum().reset_index().to_string(index=False)
outpatient_matrix = outpatient_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum().reset_index().to_string(index=False) if not outpatient_df.empty else "No Outpatient Data"
jcode_matrix = j_code_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum().reset_index().to_string(index=False) if not j_code_df.empty else "No J-Code Data"
pft_matrix = pft_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum().reset_index().to_string(index=False) if not pft_df.empty else "No PFT Data"

if st.button("Generate Segmented Executive Briefing"):
    ai_prompt = "You are a healthcare analyst evaluating a pulmonary group practice breakdown:\n\nGLOBAL TOTALS:\n" + prov_matrix + "\n\nCLINIC VISITS:\n" + outpatient_matrix + "\n\nINFUSIONS:\n" + jcode_matrix + "\n\nPFT LABS:\n" + pft_matrix + "\n\nSummarize clinic vs inpatient profiles, infusion/PFT metrics leakage, and top outlier leaks."
    try:
        # Route 1: Try your standard assigned high-end model configuration
        response = client.models.generate_content(model='gemini-3.6-flash', contents=ai_prompt)
        st.markdown(response.text)
    except Exception as primary_error:
        # Route 2: AUTOMATIC FALLBACK SAFETY NET (Routes instantly to stable workhorse model if Route 1 is overloaded)
        try:
            response = client.models.generate_content(model='gemini-1.5-flash', contents=ai_prompt)
            st.markdown(response.text)
        except Exception as fallback_error:
            st.error(f"⚠️ Google Server Capacity Limit Hit. Please tap again in a moment. (Primary Error: {str(primary_error)} | Backup Error: {str(fallback_error)})")

st.write("Ask Gemini specific questions about your metrics:")
user_query = st.text_input("Enter your natural language data question:")
if user_query:
    full_chat_summary = master_df.groupby(['Appointment / Servicing Provider', 'CPT Code'])[['Billed Charge', 'Payment', 'Units']].sum().reset_index().to_string(index=False)
    chat_prompt = "You are a medical group assistant looking at this data:\n" + full_chat_summary + "\n\nQuestion: " + user_query
    try:
        # Route 1 for Chat
        response = client.models.generate_content(model='gemini-3.6-flash', contents=chat_prompt)
        st.write(response.text)
    except Exception as chat_primary_error:
        # Route 2 Fallback for Chat
        try:
            response = client.models.generate_content(model='gemini-1.5-flash', contents=chat_prompt)
            st.write(response.text)
        except Exception as chat_fallback_error:
            st.error("⚠️ Chat traffic limit hit. Please submit your question again.")
