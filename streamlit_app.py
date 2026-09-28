import os
import io
import re
import streamlit as st
from pypdf import PdfReader
from gtts import gTTS
import speech_recognition as sr

# ---------------------------------------------------------
# 페이지 기본 설정 (스마트폰 반응형 모바일 최적화)
# ---------------------------------------------------------
st.set_page_config(
    page_title="파씨 영작문 실습",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ---------------------------------------------------------
# PDF 데이터 추출 및 캐싱 함수
# ---------------------------------------------------------
@st.cache_data
def load_lecture_data(lecture_num):
    """
    강의 번호에 맞는 PDF 파일을 탐색하여 (한글 문장, 영어 정답) 리스트 반환
    """
    # 깃허브 저장소 내 PDF 파일명 패턴 대응
    patterns = [
        f"영작문1_{lecture_num}강_예습문장.pdf",
        f"영작문1_{lecture_num}강_예습문장목록.pdf",
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
        
        # 문장 추출 정규식: 번호. 한글문장 / 영문장 형태 파싱
        # 데이터 포맷에 따라 분리 (예: 1. 한글 / Eng)
        items = []
        lines = [line.strip() for line in full_text.split("\n") if line.strip()]
        
        # 2줄씩 짝을 이루거나 특수 구분자로 되어 있는 경우 처리
        temp_kor = None
        for line in lines:
            # 한글이 포함된 경우 문제로 인식
            if re.search(r"[가-힣]", line) and not temp_kor:
                temp_kor = line
            # 영문이 주를 이루는 경우 정답으로 인식
            elif re.search(r"[a-zA-Z]", line) and temp_kor:
                items.append({
                    "kor": temp_kor,
                    "eng": line
                })
                temp_kor = None
        return items
    except Exception as e:
        st.error(f"PDF 파싱 중 오류 발생: {e}")
        return []

def generate_tts_audio(text):
    """영문 텍스트를 음성(mp3) 바이트 스트림으로 변환"""
    tts = gTTS(text=text, lang="en", tld="com")
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp

def evaluate_speech(audio_file, target_text):
    """스마트폰/마이크 오디오 입력을 STT로 인식하여 정답 비교"""
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)
            recognized_text = recognizer.recognize_google(audio_data, language="en-US")
            
            # 구두점 제거 및 소문자 정규화 비교
            clean_rec = re.sub(r"[^\w\s]", "", recognized_text).strip().lower()
            clean_ans = re.sub(r"[^\w\s]", "", target_text).strip().lower()
            
            is_correct = clean_rec == clean_ans
            return recognized_text, is_correct
    except sr.UnknownValueError:
        return "음성을 명확하게 인식하지 못했습니다. 다시 녹음해 주세요.", False
    except Exception as e:
        return f"인식 오류 발생: {e}", False

# ---------------------------------------------------------
# 세션 상태(State) 관리
# ---------------------------------------------------------
if "idx" not in st.session_state:
    st.session_state.idx = 0
if "current_lecture" not in st.session_state:
    st.session_state.current_lecture = "1강"

# ---------------------------------------------------------
# 메인 UI
# ---------------------------------------------------------
st.title("파씨 스터디 영작문 실습")

tab1, tab2 = st.tabs(["학습 및 녹음 실습", "예문 등록 (교안 관리)"])

with tab1:
    col_sel, col_stat = st.columns([2, 1])
    with col_sel:
        lecture_options = [f"{i}강" for i in range(1, 21)]
        selected_lecture = st.selectbox("강의 선택", options=lecture_options, index=0)
        
        # 강의 변경 시 인덱스 초기화
        if selected_lecture != st.session_state.current_lecture:
            st.session_state.current_lecture = selected_lecture
            st.session_state.idx = 0
            st.rerun()

    lecture_num = int(re.findall(r"\d+", st.session_state.current_lecture)[0])
    data = load_lecture_data(lecture_num)

    if not data:
        st.warning(f"현재 {st.session_state.current_lecture}에 등록된 PDF 교안 예문이 없습니다. 두 번째 탭에서 PDF를 등록하거나 파일명을 확인해 주세요.")
    else:
        total_count = len(data)
        curr_idx = st.session_state.idx
        item = data[curr_idx]

        with col_stat:
            st.write(f"진행도: {curr_idx + 1} / {total_count}")

        st.divider()

        # 문제 제시
        st.subheader("제시된 우리말")
        st.info(item["kor"])

        # 영작문 정답 확인 토글
        with st.expander("모범 영작 정답 및 원어민 발음 확인"):
            st.write(item["eng"])
            if st.button("원어민 발음 듣기", key="btn_tts"):
                audio_stream = generate_tts_audio(item["eng"])
                st.audio(audio_stream, format="audio/mp3")

        st.divider()

        # 스마트폰 녹음 실습 영역
        st.subheader("발음 및 말하기 실습")
        st.caption("스마트폰 마이크를 켜고 위 영작 정답을 읽어보세요.")
        recorded_audio = st.audio_input("마이크 녹음")

        if recorded_audio is not None:
            if st.button("내 발음 채점하기", type="primary"):
                with st.spinner("발음 분석 중..."):
                    stt_res, is_ok = evaluate_speech(recorded_audio, item["eng"])
                    
                    st.write(f"인식된 발음: {stt_res}")
                    if is_ok:
                        st.success("훌륭합니다! 정확하게 발음하셨습니다.")
                    else:
                        st.warning("정답 문장과 다소 차이가 있습니다. 다시 시도해 보세요!")

        st.divider()

        # 이전 / 다음 이동 버튼 (스마트폰 터치 편의 고려)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("◀ 이전 문장", use_container_width=True, disabled=(curr_idx == 0)):
                st.session_state.idx -= 1
                st.rerun()
        with c2:
            if st.button("다음 문장 ▶", use_container_width=True, disabled=(curr_idx >= total_count - 1)):
                st.session_state.idx += 1
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
            st.success(f"{save_filename} 파일이 정상 저장되었습니다. 새로고침 시 즉시 반영됩니다.")
            st.cache_data.clear()
