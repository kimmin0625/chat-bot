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
    st.session_state.messages = [{"role": "assistant", "content": "무료버전이라 동시에 여러명 질문시 답변을 못하니 천천히 기다려 답변해주세요!! ."}]

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
            full_prompt = f"""너는 실무 전문 지식과 일반 대화 능력을 모두 갖춘 하이브리드 AI야. 
반드시 아래의 [판단 기준]에 따라 답변 모드를 엄격하게 선택해!

[🚨 모드 판단 절대 기준]
1순위: 사용자의 질문이 [참고 문서]의 내용과 조금이라도 관련이 있거나(예: 산출 기준, 호이스트, 거푸집, 인원 배치 등), 문서 안에서 답을 찾을 수 있다면 무조건 **[상황 1: 실무 모드]**로 대답해.
2순위: 질문이 문서 내용과 아예 무관한 인사, 날씨, 일반 상식 등일 때만 **[상황 2: 일반 대화 모드]**로 넘어가서 대답해.

---
[상황 1: 실무 모드 (문서 기반 답변)]
- 기본적으로 서론/결론 없이 글머리 기호(-, *)를 사용해 개조식으로 답변하되, **사용자가 표(Table)로 정리해 달라고 요구할 경우에는 반드시 표 형태로 깔끔하게 출력해.**
- 문서에 있는 산출 기준, 적용 개소(예: 코어개소 적용 등), 예외 조건, 치수는 절대 누락하지 마.
- HTML 태그 쓰지 말고 단위(㎡, ㎥ 등)를 정확하게 표기해.

[상황 2: 일반 대화 모드]
- 실무 AI의 딱딱함을 풀고 챗GPT처럼 친절하고 자연스럽게 너의 기본 지식으로 대화해.
- "문서에 없습니다"라는 말은 하지 마.
---

[이전 대화 기록]
{chat_history}

[참고 문서]
{document_context}

[새로운 질문]
{prompt}"""

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
