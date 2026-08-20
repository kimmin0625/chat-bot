import streamlit as st
import google.generativeai as genai
import pandas as pd
import PyPDF2
import docx
import os
import time
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# API 키 설정
MY_API_KEY = "AQ.Ab8RN6LdxBZE3F1irHRJM2kE67Nei4HuYautmedHzu1yv8Ikmg"

st.set_page_config(page_title="맞춤형 AI 챗봇", layout="wide")
st.title("🤖 SM그룹 실행편성 지침 요약 챗")
st.write("궁금하신 편성지침 편하게 질문해주세요!")

if MY_API_KEY:
    try:
        genai.configure(api_key=MY_API_KEY)
        model = genai.GenerativeModel('models/gemini-3.6-flash') # 사용하시던 모델 버전 유지
    except Exception as e:
        model = None
        st.error(f"모델 연결 실패: {e}")
else:
    model = None

# 💡 핵심: 문서를 읽고, 잘게 조각내서 도서관(FAISS)에 저장하는 함수
@st.cache_resource
def build_vector_db():
    raw_text = ""
    valid_extensions = ['.txt', '.pdf', '.docx', '.csv', '.xlsx']
    files = [f for f in os.listdir('.') if os.path.isfile(f) and os.path.splitext(f)[1].lower() in valid_extensions]
    
    if not files:
        return None
        
    for file_name in files:
        try:
            if file_name.endswith('.txt'):
                with open(file_name, 'rb') as f:
                    raw_text += f.read().decode('utf-8') + "\n"
            elif file_name.endswith('.pdf'):
                with open(file_name, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        raw_text += page.extract_text() + "\n"
            elif file_name.endswith('.docx'):
                doc = docx.Document(file_name)
                for para in doc.paragraphs:
                    raw_text += para.text + "\n"
            elif file_name.endswith('.csv'):
                df = pd.read_csv(file_name)
                raw_text += df.to_string() + "\n"
            elif file_name.endswith('.xlsx'):
                df = pd.read_excel(file_name)
                raw_text += df.to_string() + "\n"
            raw_text += f"\n--- [출처: {file_name}] ---\n\n"
        except Exception:
            pass

    if not raw_text.strip():
        return None

    # 1. 텍스트를 500글자 단위로 잘게 쪼갭니다.
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = text_splitter.split_text(raw_text)
    
    # 2. 한국어에 특화된 무료 임베딩 모델로 조각들을 저장합니다.
    embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sroberta-multitask")
    vector_db = FAISS.from_texts(chunks, embeddings)
    
    return vector_db

with st.spinner("📚 문서를 조각내어 AI 도서관을 구축하고 있습니다... (최초 1회 약 1~2분 소요)"):
    vector_db = build_vector_db()

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "도서관 구축 완료! 문서 내용에 대해 편하게 물어보세요."}]

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
        
        context = ""
        # 💡 질문이 들어오면 도서관에서 가장 관련 있는 딱 3조각만 꺼내옵니다! (토큰 폭풍 절약)
        if vector_db:
            docs = vector_db.similarity_search(prompt, k=3)
            context = "\n\n".join([f"[관련 조각 {i+1}]\n{d.page_content}" for i, d in enumerate(docs)])
        
        if context:
            full_prompt = f"""너는 제공된 문서의 내용을 바탕으로 '핵심 기준'만 빠르고 정확하게 짚어주는 실무 전문 AI야. 

[절대 지켜야 할 출력 규칙]
1. 💡 간결한 개조식 요약: 서론이나 장황한 줄글 설명은 생략하고, 핵심 내용만 글머리 기호(-, *)로 정리해.
2. 🚨 조건 누락 절대 금지: 산출 기준, 적용 개소, 예외 조건 등은 단 하나도 생략하지 마라.
3. 🧹 깔끔한 텍스트: HTML 태그 쓰지 말고 단위는 ㎡, ㎥ 등으로 정확히 표기해.

[참고 문서 조각 (이 내용만 보고 답변해!)]
{context}

[질문]
{prompt}"""
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
                        placeholder.warning(f"⏳ 구글 단속에 걸렸습니다. {20 * (attempt + 1)}초 후 자동으로 재시도합니다...")
                        time.sleep(20 * (attempt + 1)) 
                    else:
                        placeholder.error("과속 단속이 너무 심합니다. 잠시 후 다시 질문해 주세요.")
                else:
                    placeholder.error(f"오류가 발생했습니다: {e}")
                    break
