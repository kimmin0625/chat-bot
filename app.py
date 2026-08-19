import streamlit as st
import google.generativeai as genai
import pandas as pd
import PyPDF2
import docx
import os
import time

# API 키
MY_API_KEY = "AQ.Ab8RN6IUHc55e8IHtqbT9THp-d9ldt2M4A9oU9o3gI5ubrXlIQ"

st.set_page_config(page_title="맞춤형 AI 챗봇", layout="wide")
st.title("🤖 SM그룹 실행예산 편성지침!")
st.write("궁금하신 산출기준 등 편하게 물어보세요!")

if MY_API_KEY:
    try:
        genai.configure(api_key=MY_API_KEY)
        model = genai.GenerativeModel('models/gemini-3.6-flash')
    except Exception as e:
        model = None
        st.error(f"모델 연결 실패: {e}")
else:
    model = None

@st.cache_data 
def load_backend_documents():
    text = ""
    valid_extensions = ['.txt', '.pdf', '.docx', '.csv', '.xlsx']
    
    files = [f for f in os.listdir('.') if os.path.isfile(f) and os.path.splitext(f)[1].lower() in valid_extensions]
    
    for file_name in files:
        try:
            if file_name.endswith('.txt'):
                with open(file_name, 'rb') as f:
                    text += f.read().decode('utf-8') + "\\n"
            elif file_name.endswith('.pdf'):
                with open(file_name, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text += page.extract_text() + "\\n"
            elif file_name.endswith('.docx'):
                doc = docx.Document(file_name)
                for para in doc.paragraphs:
                    text += para.text + "\\n"
            elif file_name.endswith('.csv'):
                df = pd.read_csv(file_name)
                text += df.to_string() + "\\n"
            elif file_name.endswith('.xlsx'):
                df = pd.read_excel(file_name)
                text += df.to_string() + "\\n"
            text += f"\\n--- [문서: {file_name}] ---\\n\\n"
        except Exception as e:
            pass
            
    return text, files

document_context, loaded_files = load_backend_documents()

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "무엇을 도와드릴까요? 학습된 지식을 바탕으로 빠르게 답변해 드립니다."}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("챗봇에게 질문하세요..."):
    if model is None:
        st.stop()
        
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        
        if document_context:
            full_prompt = f"""너는 제공된 문서의 내용을 바탕으로 아주 상세하고 깊이 있게 설명해주는 전문 AI야. 사용자의 질문에 대해 [참고 문서]의 내용을 최대한 구체적이고 풍부하게 풀어서 상세히 답변해줘.

[절대 지켜야 할 출력 규칙]
1. 답변 작성 시 `<br>`, `<BR>` 같은 HTML 태그를 절대 사용하지 마라. 줄바꿈은 자연스러운 문단 나누기(엔터)로만 처리해.
2. 단위(m2, m3 등)나 수식을 출력할 때 문자가 중복해서 나오거나(`m2 m2`), 원시 코드(`TEXT`, `\text{{...}}`)가 화면에 노출되지 않게 해.
3. 모든 단위는 ㎡, ㎥, m², m³ 와 같은 깔끔한 특수기호를 사용하거나, 일반 한글/영문 텍스트로 단 한 번만 명확하게 작성해.
4. 문서에 없는 사실을 지어내지 말고 친절하게 설명해.

[참고 문서]
{document_context}

[질문]
{prompt}"""
        else:
            full_prompt = prompt

        try:
            response = model.generate_content(full_prompt, stream=True)
            full_text = ""
            for chunk in response:
                for char in chunk.text:
                    full_text += char
                    placeholder.markdown(full_text + "▌")
                    time.sleep(0.01) 
            
            placeholder.markdown(full_text)
            st.session_state.messages.append({"role": "assistant", "content": full_text})
        except Exception as e:
            placeholder.error(f"오류가 발생했습니다: {e}")
