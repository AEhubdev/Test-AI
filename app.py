import streamlit as st
import pandas as pd
import openai
import io

MODEL_NAME = "gpt-4o"

if "df" not in st.session_state:
    st.session_state.df = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])

if uploaded_file:
    if st.session_state.df is None:
        st.session_state.df = pd.read_excel(uploaded_file)

if st.session_state.df is not None:
    st.subheader("Current Data Preview")
    st.dataframe(st.session_state.df, use_container_width=True)

    st.divider()

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        data_summary = st.session_state.df.describe(include='all').to_string()
        columns_list = list(st.session_state.df.columns)

        system_prompt = f"""
        Columns: {columns_list}
        {data_head}
        {data_summary}

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

            if "```python" in ai_content:
                code_segment = ai_content.split("```python")[1].split("```")[0].strip()
                local_scope = {"df": st.session_state.df, "pd": pd}
                exec(code_segment, {}, local_scope)
                st.session_state.df = local_scope["df"]

            with st.chat_message("assistant"):
                st.markdown(ai_content)

            st.session_state.chat_history.append({"role": "assistant", "content": ai_content})

            if "```python" in ai_content:
                st.rerun()

        except Exception as e:

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        st.session_state.df.to_excel(writer, index=False)

    st.sidebar.download_button(
        data=buffer.getvalue(),
    )

        st.session_state.df = None
        st.session_state.chat_history = []
        st.rerun()