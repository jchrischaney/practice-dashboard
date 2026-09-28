import streamlit as st
import pandas as pd
import os
import google.genai as genai

# 1. INITIALIZE GEMINI CLIENT
client = genai.Client()
MASTER_FILE = "master_medical_data.csv"

# Configuration for Provider Security Access
# (You can customize these passwords/PINs or move them into st.secrets)
ADMIN_PASSWORD = "AdminSecure2026!"
PROVIDER_PASSWORDS = {
    # Replace these names with exact strings as they appear in 'Appointment / Servicing Provider'
    # "Provider Exact Name": "PersonalPIN"
    "DEFAULT_PROVIDER": "1234"
}

def clean_and_parse_report(uploaded_file):
    """Parses specific nested, grouped CPT Level CSV report format"""
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

# Data Load
if os.path.exists(MASTER_FILE) and os.path.getsize(MASTER_FILE) > 0:
    master_df = pd.read_csv(MASTER_FILE)
    if not master_df.empty:
        master_df['CPT Code'] = master_df['CPT Code'].astype(str).str.strip()
        financial_cols = ['Billed Charge', 'Payer Charge', 'Self Charge', 'Payment', 
                          'Contractual Adjustment', 'Patient Count', 'Claim Count', 'Units', 'Change in A/R']
        for col in financial_cols:
            if col in master_df.columns:
                master_df[col] = pd.to_numeric(master_df[col], errors='coerce').fillna(0)
else:
    master_df = pd.DataFrame()

# 3. PAGE SETUP & NAVIGATION
st.set_page_config(page_title="American Medical Group Practice Analytics", layout="wide")

# Code Sets Definition
outpatient_codes = ['99202', '99203', '99204', '99205', '99212', '99213', '99214', '99215']
bedside_procedure_codes = ['36556', '76937', '31500', '36620', '32551']
bronch_codes = ['31623', '31624', '31641', '31653', '31628', '31654']

with st.sidebar:
    st.header("🔐 Portal Selection")
    portal_mode = st.radio("Select View:", ["👨‍⚕️ Provider Personal Dashboard", "🏥 Practice Executive Overview"])
    st.divider()

# Ensure master database exists
if master_df.empty:
    st.title("🩺 American Medical Group Practice Analytics")
    st.info("Welcome! Your secure runtime database is currently blank. Please use the sidebar in Executive Overview to upload a spreadsheet report.")
    with st.sidebar:
        st.header("📥 Data Management")
        uploaded_file = st.file_uploader("Upload Monthly CPT Analysis Report (CSV)", type=["csv"])
        if uploaded_file is not None and st.button("Process & Save Analytics"):
            new_data = clean_and_parse_report(uploaded_file)
            master_df = new_data
            master_df.to_csv(MASTER_FILE, index=False)
            st.success("Successfully processed database!")
            st.rerun()
    st.stop()

# List available unique providers
all_providers = sorted(master_df['Appointment / Servicing Provider'].dropna().unique().tolist())
all_months = sorted(master_df['Upload Month'].dropna().unique().tolist()) if 'Upload Month' in master_df.columns else []

# ==========================================
# 1. PROVIDER PERSONAL DASHBOARD
# ==========================================
if portal_mode == "👨‍⚕️ Provider Personal Dashboard":
    st.title("👨‍⚕️ Clinician Performance & Reimbursement Portal")
    st.caption("Confidential Individual Productivity Scorecard")
    
    with st.sidebar:
        st.header("👤 Provider Authentication")
        selected_provider = st.selectbox("Select Your Name:", ["-- Select --"] + all_providers)
        provider_pin = st.text_input("Enter Your Secure PIN:", type="password")
        
    if selected_provider == "-- Select --":
        st.info("Please select your provider profile from the sidebar.")
        st.stop()
        
    # Permission verification
    expected_pin = PROVIDER_PASSWORDS.get(selected_provider, "0000")
    if provider_pin != expected_pin and provider_pin != ADMIN_PASSWORD:
        st.warning("🔒 Please enter a valid PIN in the sidebar to access your performance data.")
        st.stop()

    # Isolated Provider Dataframe
    prov_df = master_df[master_df['Appointment / Servicing Provider'] == selected_provider].copy()
    
    # Month Filter
    available_prov_months = sorted(prov_df['Upload Month'].dropna().unique().tolist()) if 'Upload Month' in prov_df.columns else []
    
    col_filter1, col_filter2 = st.columns([2, 2])
    with col_filter1:
        chosen_month = st.selectbox("Select Reporting Month for Detail:", available_prov_months, index=len(available_prov_months)-1 if available_prov_months else 0)

    # Calculate YTD & Monthly Totals
    month_data = prov_df[prov_df['Upload Month'] == chosen_month] if available_prov_months else prov_df
    
    m_billed = float(month_data['Billed Charge'].sum())
    m_paid = float(month_data['Payment'].sum())
    m_rate = (m_paid / m_billed * 100) if m_billed > 0 else 0
    
    ytd_billed = float(prov_df['Billed Charge'].sum())
    ytd_paid = float(prov_df['Payment'].sum())
    ytd_rate = (ytd_paid / ytd_billed * 100) if ytd_billed > 0 else 0
    
    # KPI Grid
    st.subheader(f"📊 Summary Metrics for {selected_provider}")
    k1, k2, k3 = st.columns(3)
    k1.metric(f"{chosen_month} Billed", f"${m_billed:,.2f}")
    k2.metric(f"{chosen_month} Collected", f"${m_paid:,.2f}")
    k3.metric(f"{chosen_month} Collection Rate", f"{m_rate:.1f}%")
    
    y1, y2, y3 = st.columns(3)
    y1.metric("Cumulative/YTD Billed", f"${ytd_billed:,.2f}")
    y2.metric("Cumulative/YTD Collected", f"${ytd_paid:,.2f}")
    y3.metric("Cumulative Collection Rate", f"{ytd_rate:.1f}%")
    
    st.divider()
    
    # Month-over-Month Trend Chart
    st.subheader("📈 Month-over-Month Financial Trends")
    if 'Upload Month' in prov_df.columns and len(available_prov_months) > 1:
        trend_df = prov_df.groupby('Upload Month')[['Billed Charge', 'Payment']].sum()
        st.bar_chart(trend_df)
    else:
        st.caption("Month-over-month trend will expand as successive monthly reports are uploaded.")

    st.divider()
    
    # Top 10 CPT Codes
    st.subheader(f"🏆 Top 10 Procedures by Dollars ({chosen_month})")
    top_cpts = (
        month_data.groupby('CPT Code')[['Units', 'Billed Charge', 'Payment']]
        .sum()
        .sort_values(by='Payment', ascending=False)
        .head(10)
        .reset_index()
    )
    
    top_cpts['Gross Collection %'] = (top_cpts['Payment'] / top_cpts['Billed Charge'] * 100).fillna(0).map("{:.1f}%".format)
    top_cpts['Billed Charge'] = top_cpts['Billed Charge'].map("${:,.2f}".format)
    top_cpts['Payment'] = top_cpts['Payment'].map("${:,.2f}".format)
    top_cpts['Units'] = top_cpts['Units'].astype(int)
    
    st.dataframe(top_cpts, use_container_width=True, hide_index=True)

    st.divider()
    
    # Service Line Breakdown
    st.subheader("🔬 Clinical Service Breakdown")
    s_col1, s_col2, s_col3 = st.columns(3)
    
    icu_prov = month_data[month_data['CPT Code'].isin(bedside_procedure_codes)]
    bronch_prov = month_data[month_data['CPT Code'].isin(bronch_codes)]
    outpatient_prov = month_data[month_data['CPT Code'].isin(outpatient_codes)]
    
    s_col1.metric("ICU Bedside Proc Collections", f"${icu_prov['Payment'].sum():,.2f}", f"{int(icu_prov['Units'].sum())} units")
    s_col2.metric("Bronchoscopy Collections", f"${bronch_prov['Payment'].sum():,.2f}", f"{int(bronch_prov['Units'].sum())} units")
    s_col3.metric("Outpatient Clinic Collections", f"${outpatient_prov['Payment'].sum():,.2f}", f"{int(outpatient_prov['Units'].sum())} units")

# ==========================================
# 2. PRACTICE EXECUTIVE OVERVIEW
# ==========================================
else:
    st.title("🩺 American Medical Group Practice Analytics")
    st.subheader("Executive Financial & Productivity Copilot")
    
    with st.sidebar:
        st.header("🔐 Admin Gate")
        admin_auth = st.text_input("Enter Admin Password:", type="password")
        if admin_auth != ADMIN_PASSWORD:
            st.warning("Enter the Admin password to upload data or view group-wide analytics.")
            st.stop()
            
        st.header("📥 Data Management")
        uploaded_file = st.file_uploader("Upload Monthly CPT Analysis Report (CSV)", type=["csv"])
        
        if uploaded_file is not None and st.button("Process & Save Analytics"):
            new_data = clean_and_parse_report(uploaded_file)
            master_df = pd.concat([master_df, new_data], ignore_index=True)
            master_df.to_csv(MASTER_FILE, index=False)
            st.success("Successfully processed database!")
            st.rerun()
            
        if st.button("Clear Practice Database"):
            if os.path.exists(MASTER_FILE):
                os.remove(MASTER_FILE)
            st.warning("Database cleared.")
            st.rerun()
            
        st.divider()
        st.markdown("**📁 Export Options**")
        csv_data = master_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Master CSV",
            data=csv_data,
            file_name="Master_Practice_Analytics.csv",
            mime="text/csv",
        )

    # Practice Dashboard View
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

    with line_col1:
        st.markdown("**🏥 Outpatient Clinic Numbers by Provider**")
        outpatient_df = master_df[master_df['CPT Code'].isin(outpatient_codes)]
        if not outpatient_df.empty:
            st.bar_chart(outpatient_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum())
        else:
            st.caption("No matching Outpatient data found.")

    with line_col2:
        st.markdown("**🏥 Inpatient Hospital & Critical Care (E&M) by Provider**")
        inpatient_df = master_df[
            (~master_df['CPT Code'].isin(outpatient_codes)) & 
            (~master_df['CPT Code'].isin(bedside_procedure_codes)) &
            (~master_df['CPT Code'].isin(bronch_codes)) &
            (~master_df['CPT Code'].str.startswith('J', na=False)) & 
            (~master_df['CPT Code'].str.startswith('Q', na=False))
        ]
        inpatient_df = inpatient_df[~inpatient_df['CPT Code'].str.match(r'^94[0-7]\d\d', na=False)]
        if not inpatient_df.empty:
            st.bar_chart(inpatient_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum())
        else:
            st.caption("No matching Inpatient E&M data found.")

    st.divider()
    st.subheader("🫁 Pulmonary & Critical Care Procedures")
    proc_col1, proc_col2 = st.columns(2)

    with proc_col1:
        st.markdown("**🩸 ICU Bedside Procedures by Provider**")
        st.caption("CVC (36556), US Guide (76937), Intubation (31500), A-Line (36620), Chest Tube (32551)")
        icu_proc_df = master_df[master_df['CPT Code'].isin(bedside_procedure_codes)]
        if not icu_proc_df.empty:
            st.bar_chart(icu_proc_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum())
        else:
            st.caption("No matching ICU Bedside Procedure data found.")

    with proc_col2:
        st.markdown("**🔬 Bronchoscopy Suite by Provider**")
        st.caption("Diagnostic, BAL, Biopsy, Navigation, & Therapeutic (31623-31654 series)")
        bronch_df = master_df[master_df['CPT Code'].isin(bronch_codes)]
        if not bronch_df.empty:
            st.bar_chart(bronch_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum())
        else:
            st.caption("No matching Bronchoscopy data found.")

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
    icu_proc_matrix = icu_proc_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum().reset_index().to_string(index=False) if not icu_proc_df.empty else "No Bedside Proc Data"
    bronch_matrix = bronch_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum().reset_index().to_string(index=False) if not bronch_df.empty else "No Bronch Data"
    jcode_matrix = j_code_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum().reset_index().to_string(index=False) if not j_code_df.empty else "No J-Code Data"
    pft_matrix = pft_df.groupby('Appointment / Servicing Provider')[['Billed Charge', 'Payment']].sum().reset_index().to_string(index=False) if not pft_df.empty else "No PFT Data"

    if st.button("Generate Segmented Executive Briefing"):
        ai_prompt = (
            "You are a healthcare analyst evaluating a pulmonary and critical care group practice breakdown:\n\n"
            "GLOBAL TOTALS:\n" + prov_matrix + "\n\n"
            "CLINIC VISITS:\n" + outpatient_matrix + "\n\n"
            "ICU BEDSIDE PROCEDURES (Lines/Tubes/Intubations):\n" + icu_proc_matrix + "\n\n"
            "BRONCHOSCOPY PROCEDURES:\n" + bronch_matrix + "\n\n"
            "INFUSIONS:\n" + jcode_matrix + "\n\n"
            "PFT LABS:\n" + pft_matrix + "\n\n"
            "Summarize clinic vs inpatient profiles, procedural productivity (ICU vs Bronch), infusion/PFT metrics leakage, and top outlier leaks."
        )
        try:
            response = client.models.generate_content(model='gemini-2.5-flash', contents=ai_prompt)
            st.markdown(response.text)
        except Exception as api_error:
            st.error(f"⚠️ AI Alert: {str(api_error)}")

    st.write("Ask Gemini specific questions about your metrics:")
    user_query = st.text_input("Enter your natural language data question:")
    if user_query:
        full_chat_summary = master_df.groupby(['Appointment / Servicing Provider', 'CPT Code'])[['Billed Charge', 'Payment', 'Units']].sum().reset_index().to_string(index=False)
        chat_prompt = "You are a medical group assistant looking at this data:\n" + full_chat_summary + "\n\nQuestion: " + user_query
        try:
            response = client.models.generate_content(model='gemini-2.5-flash', contents=chat_prompt)
            st.write(response.text)
        except Exception as chat_error:
            st.error(f"⚠️ Chat Alert: {str(chat_error)}")
