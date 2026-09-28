import streamlit as st
import pandas as pd
import os
import google.genai as genai

# 1. INITIALIZE GEMINI CLIENT & CONSTANTS
client = genai.Client()
MASTER_FILE = "master_medical_data.csv"

# Configuration for Provider Security Access
ADMIN_PASSWORD = "AdminSecure2026!"

PROVIDER_PASSWORDS = {
    # Physicians
    "Chaney, John C": "8138",
    "Shih, Peter H": "0813",
    "Rustmann, Walter C": "6362",
    "Yuhico, Luke Simon OLIVERA": "6037",
    "Korzhuk, Tolya": "6900",                     # Update if eCW formats differently
    
    # Advanced Practice Providers (APRNs & PAs)
    "Richard, Helena S": "6626",
    "Tudlong, Marlon K": "6246",
    "Grimes, Brittany N": "4776",
    "Hinojosa, Eric D": "6809",
    "Singh, Poorita M": "0000",
    "Burton, Kevin": "0000",                      # Effective 1/1/2027
}

def clean_and_parse_report(uploaded_file, batch_label):
    """Parses specific nested, grouped CPT Level report format (CSV or Excel)"""
    if uploaded_file.name.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(uploaded_file, skiprows=5)
    else:
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
            
    # Tag rows with the custom reporting period chosen by user
    df['Upload Month'] = batch_label.strip() if batch_label.strip() else pd.Timestamp.now().strftime('%B %Y')
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
    st.info("Welcome! Your runtime database is currently blank. Please upload your reports using the sidebar.")
    with st.sidebar:
        st.header("📥 Data Management")
        uploaded_file = st.file_uploader("Upload Monthly CPT Analysis Report (CSV or Excel)", type=["csv", "xlsx", "xls"])
        batch_label = st.text_input("Reporting Period / Batch Label:", value="May-July 2026", help="e.g., 'May-July 2026', 'August 2026'")
        
        if uploaded_file is not None and st.button("Process & Save Analytics"):
            new_data = clean_and_parse_report(uploaded_file, batch_label)
            master_df = new_data
            master_df.to_csv(MASTER_FILE, index=False)
            st.success(f"Successfully processed and tagged as '{batch_label}'!")
            st.rerun()
    st.stop()

# Helper to get unique upload batches while preserving order of appearance
def get_ordered_batches(df):
    if 'Upload Month' not in df.columns:
        return []
    return list(dict.fromkeys(df['Upload Month'].dropna().tolist()))

all_providers = sorted(master_df['Appointment / Servicing Provider'].dropna().unique().tolist())
all_batches = get_ordered_batches(master_df)

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
        st.info("Please select your provider profile from the sidebar to continue.")
        st.stop()
        
    # Permission verification
    expected_pin = PROVIDER_PASSWORDS.get(selected_provider, "0000")
    if provider_pin != expected_pin and provider_pin != ADMIN_PASSWORD:
        st.warning("🔒 Please enter a valid PIN in the sidebar to access your performance data.")
        st.stop()

    # Isolated Provider Dataframe
    prov_df = master_df[master_df['Appointment / Servicing Provider'] == selected_provider].copy()
    available_prov_batches = get_ordered_batches(prov_df)
    
    col_filter1, col_filter2 = st.columns([2, 2])
    with col_filter1:
        chosen_batch = st.selectbox(
            "Select Reporting Period for Detail:", 
            available_prov_batches, 
            index=len(available_prov_batches)-1 if available_prov_batches else 0
        )

    # Calculate Period & Cumulative Totals
    batch_data = prov_df[prov_df['Upload Month'] == chosen_batch] if available_prov_batches else prov_df
    
    m_billed = float(batch_data['Billed Charge'].sum())
    m_paid = float(batch_data['Payment'].sum())
    m_rate = (m_paid / m_billed * 100) if m_billed > 0 else 0
    
    ytd_billed = float(prov_df['Billed Charge'].sum())
    ytd_paid = float(prov_df['Payment'].sum())
    ytd_rate = (ytd_paid / ytd_billed * 100) if ytd_billed > 0 else 0
    
    # KPI Grid
    st.subheader(f"📊 Summary Metrics for {selected_provider}")
    k1, k2, k3 = st.columns(3)
    k1.metric(f"{chosen_batch} Billed", f"${m_billed:,.2f}")
    k2.metric(f"{chosen_batch} Collected", f"${m_paid:,.2f}")
    k3.metric(f"{chosen_batch} Collection Rate", f"{m_rate:.1f}%")
    
    y1, y2, y3 = st.columns(3)
    y1.metric("Cumulative/YTD Billed", f"${ytd_billed:,.2f}")
    y2.metric("Cumulative/YTD Collected", f"${ytd_paid:,.2f}")
    y3.metric("Cumulative Collection Rate", f"{ytd_rate:.1f}%")
    
    st.divider()
    
    # Trend Chart Across Upload Periods
    st.subheader("📈 Performance Trends by Reporting Period")
    if len(available_prov_batches) > 1:
        trend_df = prov_df.groupby('Upload Month', sort=False)[['Billed Charge', 'Payment']].sum()
        st.bar_chart(trend_df)
    else:
        st.caption("Trends across reporting periods will display here as additional batches are uploaded.")

    st.divider()
    
    # Top 10 CPT Codes for Selected Period
    st.subheader(f"🏆 Top 10 Procedures by Dollars ({chosen_batch})")
    top_cpts = (
        batch_data.groupby('CPT Code')[['Units', 'Billed Charge', 'Payment']]
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
    
    # Service Line Breakdown for Selected Period
    st.subheader(f"🔬 Clinical Service Breakdown ({chosen_batch})")
    s_col1, s_col2, s_col3 = st.columns(3)
    
    icu_prov = batch_data[batch_data['CPT Code'].isin(bedside_procedure_codes)]
    bronch_prov = batch_data[batch_data['CPT Code'].isin(bronch_codes)]
    outpatient_prov = batch_data[batch_data['CPT Code'].isin(outpatient_codes)]
    
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
        uploaded_file = st.file_uploader("Upload Monthly CPT Analysis Report (CSV or Excel)", type=["csv", "xlsx", "xls"])
        batch_label = st.text_input("Reporting Period / Batch Label:", value="August 2026", help="Specify label, e.g. 'May-July 2026', 'August 2026'")
        
        if uploaded_file is not None and st.button("Process & Save Analytics"):
            new_data = clean_and_parse_report(uploaded_file, batch_label)
            master_df = pd.concat([master_df, new_data], ignore_index=True)
            master_df.to_csv(MASTER_FILE, index=False)
            st.success(f"Successfully processed and tagged as '{batch_label}'!")
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
            label="📥 Download Master CSV for Google Sheets",
            data=csv_data,
            file_name="Master_Practice_Analytics.csv",
            mime="text/csv",
        )
        
        with st.expander("📋 CPT Code Quick-Reference Cheat Sheet", expanded=False):
            st.markdown(
                "**E&M - CRITICAL CARE**\n"
                "* **99291** : Critical Care (30–74 min)\n"
                "* **99292** : Critical Care (Addl 30 min)\n\n"
                "**E&M - CLINIC VISITS**\n"
                "* **99202-99205** : New Patient Clinic\n"
                "* **99212-99215** : Established Patient Clinic\n\n"
                "**BEDSIDE ICU PROCEDURES**\n"
                "* **36556** : Central Venous Catheter\n"
                "* **76937** : US Guidance Vascular Access\n"
                "* **31500** : Endotracheal Intubation\n"
                "* **36620** : Arterial Line Placement\n"
                "* **32551** : Chest Tube Insertion\n\n"
                "**BRONCHOSCOPY**\n"
                "* **31623, 31624, 31628, 31641, 31653, 31654**\n\n"
                "**DIAGNOSTICS & PFT LAB**\n"
                "* **94010-94799** : Complete Pulmonary Function Panel"
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
            st.error(f"⚠️ Chat Alert: {str(chat
