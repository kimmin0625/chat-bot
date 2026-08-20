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
st.title("🤖 SM그룹 실행예산 편성지침 요약 챗봇")

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
            full_prompt = f"""너는 오직 [참고 문서]에 작성된 데이터만 추출하여 보여주는 '초정밀 데이터 추출 엔진'이다.
너의 사전 지식, 추론, 요약하려는 습성은 완벽하게 배제하고, 기계처럼 아래의 [절대 규칙]을 엄수하라.

[🚨 절대 규칙 : 위반 시 시스템 오류로 간주함]
1. 완벽한 팩트 복사: 문서에 명시된 텍스트, 숫자, 단위(㎡, ㎥, TON 등), 산출식은 토씨 하나 바꾸지 말고 원본 그대로 출력하라. 임의로 반올림하거나 말을 바꾸지 마라.
2. 조건 누락 절대 금지: '적용 개소(예: 코어개소)', '미표기 시 기준', '예외 지침' 등 괄호 안이나 비고란에 있는 조건도 100% 찾아내어 답변에 포함하라.
3. 표(Table) 출력의 의무:
   - 사용자가 "표로 나타내줘", "환산수량" 등을 요구하거나, 원본 문서의 데이터가 여러 항목과 수치로 나열되어 있다면 **반드시 마크다운(Markdown) 표 형식**으로 깔끔하게 그려라.
   - 표를 그릴 때 임의로 항목을 생략하거나 합치지 마라.
4. 환각(거짓말) 원천 차단: 질문에 대한 답이 [참고 문서]에 명확히 없다면, 절대 유추하거나 지어내지 말고 "제공된 문서에서 해당 내용을 확인할 수 없습니다."라는 단 한 문장만 출력하라.

[이전 검색 기록]
{chat_history}

[참고 문서 (이 안에서만 검색하라)]
{document_context}

[사용자 질문]
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
