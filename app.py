import streamlit as st
import pandas as pd
import openai
import io

# --- Configuration ---
OPENAI_API_KEY = "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"
MODEL_NAME = "gpt-4o"

client = openai.OpenAI(api_key=OPENAI_API_KEY)

st.set_page_config(page_title="AI Spreadsheet Engineer", layout="wide")

# --- Session State Management ---
if "df" not in st.session_state:
    st.session_state.df = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- UI Layout ---
st.title("🚀 AI Spreadsheet Engineer")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])

if uploaded_file:
    if st.session_state.df is None:
        st.session_state.df = pd.read_excel(uploaded_file)

if st.session_state.df is not None:
    # 1. Preview Area
    st.subheader("Current Data Preview")
    st.dataframe(st.session_state.df, use_container_width=True)

    # 2. Chat Area
    st.divider()
    st.subheader("Analysis & Editing")

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input(
            "Ask a question or give a command (e.g., 'What is the average age?' or 'Delete column X')"):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # PREPARE DATA CONTEXT FOR AI
        # We give the AI a summary of the data so it can answer questions directly
        data_summary = st.session_state.df.describe(include='all').to_string()
        data_head = st.session_state.df.head(5).to_string()
        columns_list = list(st.session_state.df.columns)

        system_prompt = f"""
        You are a Data Expert. You have access to a pandas DataFrame called 'df'.

        DATA CONTEXT:
        Columns: {columns_list}
        Data Preview (First 5 rows):
        {data_head}

        Data Stats:
        {data_summary}

        YOUR GOAL:
        1. If the user asks a QUESTION (e.g., "What is the total income?"), calculate the answer using the context provided and answer directly in plain text.
        2. If the user gives a COMMAND to change the data (e.g., "Add a tax column", "Format names to uppercase"), provide the Python code wrapped in ```python blocks.
        3. You can do BOTH in one response if needed.
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

            # Check if AI provided code to execute
            if "```python" in ai_content:
                code_segment = ai_content.split("```python")[1].split("```")[0].strip()
                local_scope = {"df": st.session_state.df, "pd": pd}
                exec(code_segment, {}, local_scope)
                st.session_state.df = local_scope["df"]
                st.success("Data updated!")
                # We don't trigger st.rerun() immediately so the user can see the text response first

            with st.chat_message("assistant"):
                st.markdown(ai_content)

            st.session_state.chat_history.append({"role": "assistant", "content": ai_content})

            # Refresh to show changes in the table
            if "```python" in ai_content:
                st.rerun()

        except Exception as e:
            st.error(f"Error: {str(e)}")

    # --- Sidebar Download ---
    st.sidebar.header("Export")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        st.session_state.df.to_excel(writer, index=False)

    st.sidebar.download_button(
        label="Download Final Excel",
        data=buffer.getvalue(),
        file_name="edited_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    if st.sidebar.button("Clear Everything"):
        st.session_state.df = None
        st.session_state.chat_history = []
        st.rerun()