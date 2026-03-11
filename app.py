import streamlit as st
import pandas as pd
import openai
import io
import re
import matplotlib.pyplot as plt
import seaborn as sns
from PyPDF2 import PdfReader
from pptx import Presentation

# --- 1. Page Config & Styling ---
st.set_page_config(page_title="AI Multi-Agent Workspace", layout="wide")
st.markdown("""
    <style>
    .stChatMessage { border-radius: 10px; margin-bottom: 10px; }
    .stDataFrame { border: 1px solid #444; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. Security Gatekeeper ---
if "openai_key" not in st.session_state:
    st.session_state.openai_key = None

if st.session_state.openai_key is None:
    st.title("🛡️ Enterprise AI Workspace")
    col1, col2 = st.columns([2, 1])
    with col1:
        key_input = st.text_input("Enter OpenAI API Key", type="password", placeholder="sk-...")
        if st.button("Unlock Advanced Features", use_container_width=True):
            if key_input.startswith("sk-"):
                st.session_state.openai_key = key_input
                st.rerun()
            else:
                st.error("Invalid API Key format.")
    st.stop()

# --- 3. Initialization ---
client = openai.OpenAI(api_key=st.session_state.openai_key)
MODEL = "gpt-4o"

if "files" not in st.session_state:
    st.session_state.files = {}  # Stores filename: content
if "history" not in st.session_state:
    st.session_state.history = []


# --- 4. Advanced File Parsers ---
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
            text = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"): text.append(shape.text)
            return "\n".join(text)
    except Exception as e:
        return f"Error loading file: {e}"
    return None


# --- 5. Sidebar & File Management ---
with st.sidebar:
    st.header("📂 Data Center")
    uploads = st.file_uploader("Upload Files",
                               type=["csv", "xlsx", "pdf", "pptx"],
                               accept_multiple_files=True)

    if uploads:
        for f in uploads:
            if f.name not in st.session_state.files:
                with st.spinner(f"Processing {f.name}..."):
                    st.session_state.files[f.name] = load_file(f)

    if st.button("Reset Environment", type="primary"):
        st.session_state.files = {}
        st.session_state.history = []
        st.rerun()

    st.divider()
    st.subheader("Active Files")
    for fn in st.session_state.files.keys():
        st.caption(f"✅ {fn}")

# --- 6. Main Interface ---
st.title("🤖 Multi-File Analytics Agent")

# Previews
if st.session_state.files:
    tabs = st.tabs([f"📄 {fn[:15]}..." for fn in st.session_state.files.keys()])
    for i, (fn, content) in enumerate(st.session_state.files.items()):
        with tabs[i]:
            if isinstance(content, pd.DataFrame):
                st.dataframe(content, height=250)
                st.info(f"Shape: {content.shape[0]} rows, {content.shape[1]} columns")
            else:
                st.text_area("Content Preview", content[:1000], height=200)

# Chat Loop
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "fig" in msg: st.pyplot(msg["fig"])

if prompt := st.chat_input(
        "Ask anything (e.g., 'Compare the total sales in file1 vs file2' or 'Plot a histogram of prices')"):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 7. AI Logic & Execution Environment
    context = "You have the following files available:\n"
    exec_locals = {"pd": pd, "plt": plt, "sns": sns, "plt_show": plt.show}

    for fn, content in st.session_state.files.items():
        var_name = re.sub(r'[^a-zA-Z0-9]', '_', fn)
        exec_locals[var_name] = content
        if isinstance(content, pd.DataFrame):
            context += f"- DataFrame '{var_name}' (from {fn}): Columns: {list(content.columns)}\n"
        else:
            context += f"- Document '{var_name}' (from {fn}): Text content available.\n"

    system_msg = f"""
    {context}
    You are a super-intelligent Data Engineer.
    1. For analysis: Speak naturally.
    2. For data changes/visuals: Provide code in ```python blocks.
    3. Always update the variables in the dictionary if you modify data.
    4. To show a plot, use 'plt.gcf()' at the end of the block.
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
            # Intercept plots
            plt.close('all')
            exec(code, {}, exec_locals)

            # Update Session State with modified DataFrames
            for var_name, obj in exec_locals.items():
                for fn in st.session_state.files.keys():
                    if re.sub(r'[^a-zA-Z0-9]', '_', fn) == var_name and isinstance(obj, pd.DataFrame):
                        st.session_state.files[fn] = obj

            if plt.get_fignums():
                fig = plt.gcf()

        with st.chat_message("assistant"):
            st.markdown(ai_resp)
            if fig: st.pyplot(fig)

        history_entry = {"role": "assistant", "content": ai_resp}
        if fig: history_entry["fig"] = fig
        st.session_state.history.append(history_entry)

        if "```python" in ai_resp and not fig:
            st.rerun()

    except Exception as e:
        st.error(f"Execution Error: {e}")

# --- 8. Download Portal ---
if st.session_state.files:
    st.sidebar.divider()
    st.sidebar.subheader("📥 Export Results")
    for fn, content in st.session_state.files.items():
        if isinstance(content, pd.DataFrame):
            out = io.BytesIO()
            content.to_excel(out, index=False)
            st.sidebar.download_button(f"Download {fn}", out.getvalue(), f"updated_{fn}.xlsx")