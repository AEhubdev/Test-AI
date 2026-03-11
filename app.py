import streamlit as st
import pandas as pd
import openai
import io
import re
import matplotlib.pyplot as plt
import seaborn as sns
from PyPDF2 import PdfReader
from pptx import Presentation

# --- 1. Page Config ---
st.set_page_config(page_title="Ultimate AI Data Agent", layout="wide")

# --- 2. API Key Gatekeeper ---
if "openai_key" not in st.session_state:
    st.session_state.openai_key = None

if st.session_state.openai_key is None:
    st.title("🛡️ Enterprise AI Data Agent")
    user_key = st.text_input("Enter OpenAI API Key", type="password", placeholder="sk-...")
    if st.button("Unlock System"):
        if user_key.startswith("sk-"):
            st.session_state.openai_key = user_key
            st.rerun()
    st.stop()

# --- 3. Initialize OpenAI & State ---
client = openai.OpenAI(api_key=st.session_state.openai_key)
MODEL = "gpt-4o"

if "files" not in st.session_state:
    st.session_state.files = {}
if "history" not in st.session_state:
    st.session_state.history = []


# --- 4. File Parsers ---
def load_file(uploaded_file):
    name = uploaded_file.name
    try:
        if name.endswith(('.xlsx', '.xls')):
            return pd.read_excel(uploaded_file)
        elif name.endswith('.csv'):
            return pd.read_csv(uploaded_file)
        elif name.endswith('.pdf'):
            reader = PdfReader(uploaded_file)
            return "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
        elif name.endswith('.pptx'):
            prs = Presentation(uploaded_file)
            text = [shape.text for slide in prs.slides for shape in slide.shapes if hasattr(shape, "text")]
            return "\n".join(text)
    except Exception as e:
        return f"Error: {e}"
    return None


# --- 5. Sidebar ---
with st.sidebar:
    st.header("📂 Upload Center")
    uploads = st.file_uploader("Upload Data/Docs", type=["csv", "xlsx", "pdf", "pptx"], accept_multiple_files=True)
    if uploads:
        for f in uploads:
            if f.name not in st.session_state.files:
                st.session_state.files[f.name] = load_file(f)

    if st.button("Reset All", type="primary"):
        st.session_state.files = {}
        st.session_state.history = []
        st.rerun()

# --- 6. Main Workspace ---
st.title("🤖 Multi-Modal Data Scientist")

if st.session_state.files:
    # Preview Tabs
    tabs = st.tabs([f"📄 {fn}" for fn in st.session_state.files.keys()])
    for i, (fn, content) in enumerate(st.session_state.files.items()):
        with tabs[i]:
            if isinstance(content, pd.DataFrame):
                st.dataframe(content, height=250)
            else:
                st.text_area("Content", content[:1000], height=200)

# Chat Display
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "fig" in msg: st.pyplot(msg["fig"])

# --- 7. The Intelligence Engine ---
if prompt := st.chat_input("Ask a question or give a command..."):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Building Environment
    exec_locals = {"pd": pd, "plt": plt, "sns": sns}
    context_str = "You have access to these variables in memory. DO NOT try to load files from disk.\n"

    for fn, content in st.session_state.files.items():
        # Create a clean variable name (e.g. data_csv)
        var_name = re.sub(r'[^a-zA-Z0-9]', '_', fn)
        exec_locals[var_name] = content
        if isinstance(content, pd.DataFrame):
            context_str += f"- Variable `{var_name}`: DataFrame from '{fn}'. Columns: {list(content.columns)}\n"
        else:
            context_str += f"- Variable `{var_name}`: Text from document '{fn}'.\n"

    system_msg = f"""
    {context_str}

    CRITICAL RULES:
    1. NEVER use `pd.read_excel`, `pd.read_csv`, or `to_excel`. The files are ALREADY in memory as variables.
    2. To modify a file, update its variable (e.g., `data_csv = data_csv.drop(...)`).
    3. To visualize, use `plt.figure()`. Do NOT use `plt.show()`. Use `plt.gcf()` at the end of the code block.
    4. Provide Python code ONLY in ```python blocks.
    """

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": system_msg}] + st.session_state.history[-5:]
        )
        ai_resp = response.choices[0].message.content

        fig = None
        if "```python" in ai_resp:
            code = ai_resp.split("```python")[1].split("```")[0].strip()

            # Clean up old plots
            plt.close('all')

            # RUN THE CODE
            exec(code, {}, exec_locals)

            # Update Session State with modified DataFrames
            for var_name, obj in exec_locals.items():
                for fn in st.session_state.files.keys():
                    if re.sub(r'[^a-zA-Z0-9]', '_', fn) == var_name:
                        st.session_state.files[fn] = obj

            # Capture Figure if any
            if plt.get_fignums():
                fig = plt.gcf()

        with st.chat_message("assistant"):
            st.markdown(ai_resp)
            if fig: st.pyplot(fig)

        entry = {"role": "assistant", "content": ai_resp}
        if fig: entry["fig"] = fig
        st.session_state.history.append(entry)

        if "```python" in ai_resp and not fig:
            st.rerun()

    except Exception as e:
        st.error(f"Execution Error: {e}")

# --- 8. Export Manager ---
if st.session_state.files:
    st.sidebar.divider()
    st.sidebar.subheader("📥 Export Dataframes")
    for fn, content in st.session_state.files.items():
        if isinstance(content, pd.DataFrame):
            buf = io.BytesIO()
            content.to_excel(buf, index=False)
            st.sidebar.download_button(f"Save {fn}", buf.getvalue(), f"updated_{fn}.xlsx", use_container_width=True)