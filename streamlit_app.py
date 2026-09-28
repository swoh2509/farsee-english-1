
import os
import io
import re
import streamlit as st
from pypdf import PdfReader
from gtts import gTTS
import speech_recognition as sr

st.set_page_config(
    page_title="파씨 영작문 실습",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="collapsed"
)

@st.cache_data
def load_lecture_data(lecture_num):
    patterns = [
        f"영작문1_{lecture_num}강_예습문장목록.pdf",
        f"영작문1_{lecture_num}강_예습문장.pdf",
        f"영작문1_{lecture_num}강.pdf"
    ]
    target_path = None
    for p in patterns:
        if os.path.exists(p):
            target_path = p
            break
    if not target_path:
        return []

    try:
        reader = PdfReader(target_path)
        full_text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                full_text += t + "\n"
        
        items = []
        tokens = re.split(r'\n\s*(\d{1,2})[\.\)]\s*', '\n' + full_text)
        for i in range(1, len(tokens), 2):
            q_num = tokens[i]
            block = tokens[i+1].strip()
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            if not lines:
                continue
            eng_parts = []
            kor_parts = []
            for line in lines:
                if re.search(r'[가-힣]', line):
                    kor_parts.append(line)
                else:
                    eng_parts.append(line)
            eng_sentence = " ".join(eng_parts).strip() if eng_parts else ""
            kor_sentence = " ".join(kor_parts).strip() if kor_parts else ""
            if kor_sentence and eng_sentence:
                items.append({
                    "num": q_num,
                    "kor": kor_sentence,
                    "eng": eng_sentence
                })
        return items
    except Exception as e:
        st.error(f"PDF 파싱 오류: {e}")
        return []

def generate_tts_audio(text):
    clean_speech_text = re.sub(r"[\[\]]", "", text)
    tts = gTTS(text=clean_speech_text, lang="en", tld="com")
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp

def evaluate_speech(audio_file, target_text):
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)
            recognized_text = recognizer.recognize_google(audio_data, language="en-US")
            clean_rec = re.sub(r"[^\w\s]", "", recognized_text).strip().lower()
            clean_ans = re.sub(r"[^\w\s]", "", target_text).strip().lower()
            is_correct = clean_rec == clean_ans
            return recognized_text, is_correct
    except sr.UnknownValueError:
        return "음성을 명확하게 인식하지 못했습니다. 다시 녹음해 주세요.", False
    except Exception as e:
        return f"인식 오류 발생: {e}", False

if "idx" not in st.session_state:
    st.session_state.idx = 0
if "current_lecture" not in st.session_state:
    st.session_state.current_lecture = "1강"

st.title("파씨 스터디 영작문 실습")

tab1, tab2 = st.tabs(["학습 및 녹음 실습", "예문 등록 (교안 관리)"])

with tab1:
    col_sel, col_stat = st.columns([2, 1])
    with col_sel:
        lecture_options = [f"{i}강" for i in range(1, 21)]
        selected_lecture = st.selectbox("강의 선택", options=lecture_options, index=0)
        if selected_lecture != st.session_state.current_lecture:
            st.session_state.current_lecture = selected_lecture
            st.session_state.idx = 0
            st.rerun()

    lecture_num = int(re.findall(r"\d+", st.session_state.current_lecture)[0])
    data = load_lecture_data(lecture_num)

    if not data:
        st.warning(f"현재 {st.session_state.current_lecture}에 등록된 PDF 교안 예문이 없습니다.")
    else:
        total_count = len(data)
        curr_idx = min(st.session_state.idx, total_count - 1)
        item = data[curr_idx]

        with col_stat:
            st.write(f"진행도: {curr_idx + 1} / {total_count}")

        st.divider()

        # 1. 제시된 우리말
        st.subheader(f"제시된 우리말 (문제 {item['num']}번)")
        st.info(item["kor"])

        # 2. 직접 영작 타이핑 입력창 및 채점
        st.subheader("직접 영작해보기")
        user_typing = st.text_input("위 우리말을 보고 영어 문장을 타이핑해 보세요.", key=f"text_input_{curr_idx}")
        if st.button("영작 정답 확인", key=f"btn_check_text_{curr_idx}"):
            if not user_typing.strip():
                st.warning("문장을 먼저 입력해 주세요.")
            else:
                clean_u = re.sub(r"[^\w\s]", "", user_typing).strip().lower()
                clean_t = re.sub(r"[^\w\s]", "", item["eng"]).strip().lower()
                if clean_u == clean_t:
                    st.success("정답입니다! 완벽하게 영작하셨습니다.")
                else:
                    st.error("아쉽네요. 철자나 어순을 확인해 보세요!")

        st.divider()

        # 3. 말하기 실습 (모범 정답 확인보다 위에 배치)
        st.subheader("발음 및 말하기 실습")
        st.caption("스마트폰 마이크를 켜고 직접 영작한 문장을 소리 내어 읽어보세요.")
        recorded_audio = st.audio_input("마이크 녹음", key=f"audio_input_{curr_idx}")

        if recorded_audio is not None:
            if st.button("내 발음 채점하기", type="primary", key=f"btn_eval_{curr_idx}"):
                with st.spinner("발음 분석 중..."):
                    stt_res, is_ok = evaluate_speech(recorded_audio, item["eng"])
                    st.write(f"인식된 발음: {stt_res}")
                    if is_ok:
                        st.success("훌륭합니다! 정확하게 발음하셨습니다.")
                    else:
                        st.warning("정답 문장과 다소 차이가 있습니다. 아래 모범 정답을 확인해 보세요!")

        st.divider()

        # 4. 모범 정답 및 원어민 발음 (맨 마지막에 확인)
        with st.expander("모범 영작 정답 및 원어민 발음 확인"):
            st.markdown(item["eng"])
            if st.button("원어민 발음 듣기", key=f"btn_tts_{curr_idx}"):
                audio_stream = generate_tts_audio(item["eng"])
                st.audio(audio_stream, format="audio/mp3")

        st.divider()

        c1, c2 = st.columns(2)
        with c1:
            if st.button("◀ 이전 문장", use_container_width=True, disabled=(curr_idx == 0)):
                st.session_state.idx = curr_idx - 1
                st.rerun()
        with c2:
            if st.button("다음 문장 ▶", use_container_width=True, disabled=(curr_idx >= total_count - 1)):
                st.session_state.idx = curr_idx + 1
                st.rerun()

with tab2:
    st.subheader("강의별 PDF 교안 업로드")
    target_upload_lec = st.selectbox("등록할 강의 선택", options=[f"{i}강" for i in range(1, 21)], key="upload_sel")
    uploaded_file = st.file_uploader("PDF 교안 파일 업로드", type=["pdf"])
    
    if uploaded_file is not None:
        lec_n = re.findall(r"\d+", target_upload_lec)[0]
        save_filename = f"영작문1_{lec_n}강_예습문장.pdf"
        if st.button(f"{target_upload_lec} 교안으로 저장하기"):
            with open(save_filename, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"{save_filename} 파일이 저장되었습니다.")
            st.cache_data.clear()

