import streamlit as st
import pandas as pd
import openai
import io

# --- 1. Page Config ---
st.set_page_config(page_title="AI Spreadsheet Engineer", layout="wide")

# --- 2. API Key Gatekeeper ---
if "openai_key" not in st.session_state:
    st.session_state.openai_key = None

if st.session_state.openai_key is None:
    st.title("🔑 AI Spreadsheet Engineer")
    st.markdown("### Please enter your OpenAI API Key to begin.")

    user_key = st.text_input("OpenAI API Key", type="password", placeholder="sk-...")

    if st.button("Unlock App"):
        if user_key.startswith("sk-"):
            st.session_state.openai_key = user_key
            st.success("Key accepted!")
            st.rerun()
        else:
            st.error("Invalid key format. Please enter a valid OpenAI API key.")
    st.stop()

# --- 3. Initialize OpenAI Client & State ---
client = openai.OpenAI(api_key=st.session_state.openai_key)
MODEL_NAME = "gpt-4o"

if "df" not in st.session_state:
    st.session_state.df = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- 4. Main UI ---
st.title("📊 Data Analysis & Editing Workspace")

with st.sidebar:
    st.header("Session Control")
    if st.button("Change API Key / Logout"):
        st.session_state.openai_key = None
        st.session_state.df = None
        st.session_state.chat_history = []
        st.rerun()
    st.divider()

# UPDATED: Accept both Excel and CSV
uploaded_file = st.file_uploader("Upload Data File", type=["xlsx", "xls", "csv"])

if uploaded_file:
    if st.session_state.df is None:
        # LOGIC: Check file extension to use correct pandas reader
        if uploaded_file.name.endswith('.csv'):
            st.session_state.df = pd.read_csv(uploaded_file)
        else:
            st.session_state.df = pd.read_excel(uploaded_file)

if st.session_state.df is not None:
    # Preview Table
    st.subheader("Current Data Preview")
    st.dataframe(st.session_state.df, use_container_width=True)

    # Chat Interface
    st.divider()
    st.subheader("Chat with your Data")

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ex: 'What is the average income?' or 'Add a column for 10% bonus'"):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Context for AI
        data_summary = st.session_state.df.describe(include='all').to_string()
        data_head = st.session_state.df.head(10).to_string()
        columns_list = list(st.session_state.df.columns)

        system_prompt = f"""
        You are a Data Expert. Dataframe name is 'df'.
        Columns: {columns_list}
        Data Preview:
        {data_head}
        Stats Summary:
        {data_summary}

        GOALS:
        1. For questions: Answer directly in plain text.
        2. For data changes: Provide ONLY the Python code in ```python blocks.
        3. Use 'df' as the variable and 'pd' for pandas.
        """

        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )

            ai_content = response.choices[0].message.content

            # Execution Logic
            if "```python" in ai_content:
                code_segment = ai_content.split("```python")[1].split("```")[0].strip()
                local_scope = {"df": st.session_state.df, "pd": pd}
                exec(code_segment, {}, local_scope)
                st.session_state.df = local_scope["df"]
                st.success("Changes applied!")

            with st.chat_message("assistant"):
                st.markdown(ai_content)

            st.session_state.chat_history.append({"role": "assistant", "content": ai_content})

            if "```python" in ai_content:
                st.rerun()

        except Exception as e:
            st.error(f"Error: {str(e)}")

    # --- Export & Reset ---
    st.sidebar.header("Export Data")
    buffer = io.BytesIO()
    # We export to Excel by default for better formatting
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        st.session_state.df.to_excel(writer, index=False)

    st.sidebar.download_button(
        label="Download Updated Excel",
        data=buffer.getvalue(),
        file_name="ai_updated_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    if st.sidebar.button("Clear Data & Chat"):
        st.session_state.df = None
        st.session_state.chat_history = []
        st.rerun()