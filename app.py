import streamlit as st
import pandas as pd
import openai
import io
import re
import sys
import matplotlib.pyplot as plt
import seaborn as sns
from PyPDF2 import PdfReader
from pptx import Presentation

# --- 1. Page Config ---
st.set_page_config(page_title="Advanced AI Data Scientist", layout="wide")

# --- 2. API Key Gatekeeper ---
if "openai_key" not in st.session_state:
    st.session_state.openai_key = None

if st.session_state.openai_key is None:
    st.title("🛡️ Enterprise AI Data Agent")
    user_key = st.text_input("Enter OpenAI API Key", type="password")
    if st.button("Unlock System"):
        if user_key.startswith("sk-"):
            st.session_state.openai_key = user_key
            st.rerun()
    st.stop()

client = openai.OpenAI(api_key=st.session_state.openai_key)
MODEL = "gpt-4o"

if "files" not in st.session_state:
    st.session_state.files = {}
if "history" not in st.session_state:
    st.session_state.history = []


# --- 3. Parsers ---
def load_file(uploaded_file):
    name = uploaded_file.name
    try:
        if name.endswith(('.xlsx', '.xls')):
            return pd.read_excel(uploaded_file)
        elif name.endswith('.csv'):
            return pd.read_csv(uploaded_file)
        elif name.endswith('.pdf'):
            return "\n".join([p.extract_text() for p in PdfReader(uploaded_file).pages if p.extract_text()])
        elif name.endswith('.pptx'):
            return "\n".join(
                [s.text for sl in Presentation(uploaded_file).slides for s in sl.shapes if hasattr(s, "text")])
    except Exception as e:
        return f"Error: {e}"
    return None


# --- 4. Sidebar ---
with st.sidebar:
    st.header("📂 Data Center")
    uploads = st.file_uploader("Upload Files", type=["csv", "xlsx", "pdf", "pptx"], accept_multiple_files=True)
    if uploads:
        for f in uploads:
            if f.name not in st.session_state.files:
                st.session_state.files[f.name] = load_file(f)

    if st.button("Reset Everything", type="primary"):
        st.session_state.files = {}
        st.session_state.history = []
        st.rerun()

# --- 5. Main Workspace ---
st.title("🤖 Multi-Modal Data Scientist")

# Chat History Display
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "fig" in msg: st.pyplot(msg["fig"])

# --- 6. The Execution & Reflection Engine ---
if prompt := st.chat_input("Ask a question (e.g., 'What is the sum of Gold_Monthly_change?')"):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Prepare Context & Variables
    exec_locals = {"pd": pd, "plt": plt, "sns": sns}
    context_str = "Variables in memory:\n"
    for fn, content in st.session_state.files.items():
        var_name = re.sub(r'[^a-zA-Z0-9]', '_', fn)
        exec_locals[var_name] = content
        if isinstance(content, pd.DataFrame):
            context_str += f"- `{var_name}`: DataFrame ({fn}). Columns: {list(content.columns)}\n"
        else:
            context_str += f"- `{var_name}`: Text document ({fn})\n"

    # STEP 1: AI generates code to find the answer
    system_msg = f"""
    {context_str}
    You are a Data Scientist. To answer the user, write Python code that calculates the result.
    IMPORTANT: Print the final answer using `print()`.
    Wrap code in ```python blocks.
    """

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": system_msg}] + st.session_state.history[-5:]
        )
        ai_code_resp = response.choices[0].message.content

        # STEP 2: Execute code and capture the PRINTED output
        captured_output = ""
        fig = None
        if "```python" in ai_code_resp:
            code = ai_code_resp.split("```python")[1].split("```")[0].strip()

            # Redirect stdout to capture print() statements
            old_stdout = sys.stdout
            redirected_output = sys.stdout = io.StringIO()

            try:
                plt.close('all')
                exec(code, {}, exec_locals)
                sys.stdout = old_stdout
                captured_output = redirected_output.getvalue()

                # Update DataFrames in state if modified
                for var_name, obj in exec_locals.items():
                    for fn in st.session_state.files.keys():
                        if re.sub(r'[^a-zA-Z0-9]', '_', fn) == var_name:
                            st.session_state.files[fn] = obj

                if plt.get_fignums(): fig = plt.gcf()
            except Exception as e:
                sys.stdout = old_stdout
                captured_output = f"Execution Error: {e}"

        # STEP 3: Final "ChatGPT Style" Synthesis
        # We send the raw numbers back to the AI so it can talk to the user
        synthesis_prompt = f"""
        The user asked: "{prompt}"
        The code generated was: {ai_code_resp}
        The execution output was: "{captured_output}"

        Provide the final answer to the user in a friendly, conversational way. 
        If a calculation was made, state the result clearly.
        """

        final_response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": synthesis_prompt}]
        )
        ai_final_text = final_response.choices[0].message.content

        with st.chat_message("assistant"):
            st.markdown(ai_final_text)
            if fig: st.pyplot(fig)

        entry = {"role": "assistant", "content": ai_final_text}
        if fig: entry["fig"] = fig
        st.session_state.history.append(entry)

    except Exception as e:
        st.error(f"System Error: {e}")

# --- 7. Export Manager ---
if st.session_state.files:
    st.sidebar.divider()
    for fn, content in st.session_state.files.items():
        if isinstance(content, pd.DataFrame):
            buf = io.BytesIO()
            content.to_excel(buf, index=False)
            st.sidebar.download_button(f"📥 {fn}", buf.getvalue(), f"updated_{fn}.xlsx", use_container_width=True)