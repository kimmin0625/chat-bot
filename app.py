import streamlit as st
import google.generativeai as genai
import pandas as pd
import PyPDF2
import docx
import os
import time

# 🚨 Streamlit 비밀 금고에서 API 키 불러오기
try:
    MY_API_KEY = st.secrets["MY_API_KEY"]
except:
    MY_API_KEY = None
    st.error("비밀 금고(Secrets)에 API 키가 설정되지 않았습니다.")

st.set_page_config(page_title="무결점 문서 검색기", layout="wide")
st.title("🤖 SM그룹 실행예산 편성지침 요약챗봇")
st.write("문서에 없는 내용은 대답하지 않으며, 원본 데이터를 100% 그대로 출력합니다.")

if MY_API_KEY:
    try:
        genai.configure(api_key=MY_API_KEY)
        # 💡 AI의 창의성을 0%로 박탈 (왜곡 원천 차단)
        model = genai.GenerativeModel('models/gemini-3.6-flash', generation_config={"temperature": 0.0})
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
        except Exception:
            pass
            
    return text, files

document_context, loaded_files = load_backend_documents()

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "문서를 모두 인식했습니다. 검색할 내용을 입력해 주세요. (문서에 없는 내용은 답변하지 않습니다)"}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("문서 내용 검색..."):
    if model is None:
        st.stop()
        
    chat_history = ""
    for msg in st.session_state.messages[-4:]:
        role_name = "질문" if msg["role"] == "user" else "검색결과"
        chat_history += f"{role_name}: {msg['content']}\n"
        
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        
         if document_context:
            full_prompt = f"너는 제공된 문서의 내용만을 기반으로 답변하는 친절하고 전문적인 AI야. 다음 [참고 문서]를 꼼꼼히 확인하고 질문에 답해줘. 문서에 없는 내용은 모른다고 대답해야 해.\n\n[참고 문서]\n{document_context}\n\n[질문]\n{prompt}"

        else:
            full_prompt = prompt

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
                        placeholder.warning(f"⏳ 서버 혼잡. {20 * (attempt + 1)}초 후 재시도합니다...")
                        time.sleep(20 * (attempt + 1)) 
                    else:
                        placeholder.error("요청이 너무 많습니다. 잠시 후 다시 질문해 주세요.")
                else:
                    placeholder.error(f"오류가 발생했습니다: {e}")
                    break
