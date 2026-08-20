import streamlit as st
import google.generativeai as genai
import pandas as pd
import PyPDF2
import docx
import os
import time

# 🚨 Streamlit 비밀 금고에서 API 키 불러오기 (보안 유지)
try:
    MY_API_KEY = st.secrets["MY_API_KEY"]
except:
    MY_API_KEY = None
    st.error("비밀 금고(Secrets)에 API 키가 설정되지 않았습니다.")

st.set_page_config(page_title="맞춤형 AI 챗봇", layout="wide")
st.title("🤖 SM그룹 실행예산 편성지침")
st.write("이 챗봇은 필요한 문서를 이미 모두 학습한 상태입니다. 바로 질문해 보세요!")

if MY_API_KEY:
    try:
        genai.configure(api_key=MY_API_KEY)
        # 💡 선생님이 가장 만족하셨던 기본 모델 설정 (유연한 표 생성 가능)
       model = genai.GenerativeModel('gemini-3.6-flash')
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
                    text += f.read().decode('utf-8') + "\n"
            elif file_name.endswith('.pdf'):
                with open(file_name, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
            elif file_name.endswith('.docx'):
                doc = docx.Document(file_name)
                for para in doc.paragraphs:
                    text += para.text + "\n"
            elif file_name.endswith('.csv'):
                df = pd.read_csv(file_name)
                text += df.to_string() + "\n"
            elif file_name.endswith('.xlsx'):
                df = pd.read_excel(file_name)
                text += df.to_string() + "\n"
            text += f"\n--- [문서: {file_name}] ---\n\n"
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
        
        # 💡 선생님이 작성하셨던 가장 심플하고 훌륭한 프롬프트!
        if document_context:
            full_prompt = f"너는 제공된 문서의 내용만을 기반으로 답변하는 친절하고 전문적인 AI야. 다음 [참고 문서]를 꼼꼼히 확인하고 질문에 답해줘. 문서에 없는 내용은 모른다고 대답해야 해.\n\n[참고 문서]\n{document_context}\n\n[질문]\n{prompt}"
        else:
            full_prompt = prompt

        # 🚨 과속 단속(429 에러)이 뜰 때 뻗지 않도록 방패만 추가했습니다.
        max_retries = 3 
        for attempt in range(max_retries):
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
                break 
                
            except Exception as e:
                if "429" in str(e):
                    if attempt < max_retries - 1:
                        placeholder.warning(f"⏳ 구글 서버 혼잡. {20 * (attempt + 1)}초 후 자동으로 재시도합니다...")
                        time.sleep(20 * (attempt + 1)) 
                    else:
                        placeholder.error("요청이 너무 많습니다. 잠시 후 다시 질문해 주세요.")
                else:
                    placeholder.error(f"오류가 발생했습니다: {e}")
                    break
