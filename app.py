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
            full_prompt = f"""너는 제공된 문서의 내용을 바탕으로 '핵심 기준'만 빠르고 정확하게 짚어주는 실무 전문 AI야. 

[절대 지켜야 할 출력 규칙]
1. 💡 간결한 개조식 요약: 서론이나 장황한 줄글 설명은 모두 생략하고, 핵심 내용만 글머리 기호(-, *)를 사용하여 깔끔하게 정리해.
2. 🚨 조건 누락 절대 금지: 요약을 하더라도 '산출 기준', '적용 개소(예: 코어개소 적용 등)', '예외 조건', '치수' 등 실무에 필요한 세부 지침과 팩트는 단 하나도 생략하지 말고 무조건 리스트에 포함시켜. 
3. 🧹 깔끔한 텍스트: `<br>`, `TEXT` 같은 태그나 코드를 쓰지 말고, 단위는 ㎡, ㎥ 등으로 정확하게 표기해.

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
