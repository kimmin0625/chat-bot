import streamlit as st
import google.generativeai as genai
import pandas as pd
import PyPDF2
import docx
import os
import time

# 🚨 API 키 (새로 발급받은 키를 여기에 넣으세요)
MY_API_KEY = st.secrets["MY_API_KEY"]
st.set_page_config(page_title="맞춤형 AI 챗봇", layout="wide")
st.title("🤖 SM그룹 실행예산 편성지침 요약 챗봇!")

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
    st.session_state.messages = [{"role": "assistant", "content": "문서를 모두 외웠습니다! 이전 대화 흐름도 기억하고 있으니 편하게 질문해 주세요."}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("챗봇에게 질문하세요..."):
    if model is None:
        st.stop()
        
    # 💡 핵심: AI가 이전 문맥을 이해하도록 최근 4번의 대화 기록을 모아줍니다.
    chat_history = ""
    for msg in st.session_state.messages[-4:]:
        role_name = "질문" if msg["role"] == "user" else "AI 답변"
        chat_history += f"{role_name}: {msg['content']}\n"
        
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        
        if document_context:
            full_prompt = f"""너는 제공된 문서의 내용과 [이전 대화 기록]을 바탕으로 '핵심 기준'을 정확하게 짚어주는 실무 전문 AI야. 

[절대 지켜야 할 출력 규칙]
1. 간결한 개조식 요약: 장황한 설명은 생략하고, 글머리 기호(-, *)로 깔끔하게 정리해.
2. 조건 누락 절대 금지: 산출 기준, 적용 개소(예: 코어개소 적용), 예외 조건은 단 하나도 생략하지 마라.
3. 🧹 깔끔한 텍스트: `<br>`, `TEXT` 같은 태그 쓰지 말고 단위는 ㎡, ㎥ 등으로 정확히 표기해.
4. 문맥 유지: [이전 대화 기록]을 참고해서 사용자가 이어서 질문하면 자연스럽게 연결해서 답변해.

[이전 대화 기록]
{chat_history}

[참고 문서]
{document_context}

[새로운 질문]
{prompt}"""
        else:
            full_prompt = prompt

        max_retries = 3 
        import time
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
                        placeholder.warning(f"⏳ 구글 단속에 걸렸습니다. {20 * (attempt + 1)}초 후 자동으로 재시도합니다...")
                        time.sleep(20 * (attempt + 1)) 
                    else:
                        placeholder.error("과속 단속이 너무 심합니다. 잠시 후 다시 질문해 주세요.")
                else:
                    placeholder.error(f"오류가 발생했습니다: {e}")
                    break
