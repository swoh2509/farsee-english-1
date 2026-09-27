# -*- coding: utf-8 -*-
import os
import glob
import tempfile
import gradio as gr
import speech_recognition as sr
from gtts import gTTS
from pypdf import PdfReader

# 1강부터 20강 데이터 저장소
LECTURE_DB = {}
for i in range(1, 21):
    LECTURE_DB[str(i) + "강"] = []

def parse_pdf(fpath):
    items = []
    try:
        reader = PdfReader(fpath)
        text = ""
        for p in reader.pages:
            t = p.extract_text()
            if t:
                text += "\n" + t
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        cur_en, cur_kr, cur_nt, num = "", "", "", 1
        for line in lines:
            parts = line.split(".", 1)
            if len(parts) == 2 and parts[0].strip().isdigit():
                if cur_en and cur_kr:
                    items.append({"id": num, "korean": cur_kr, "english": cur_en, "note": cur_nt})
                    num += 1
                    cur_en, cur_kr, cur_nt = "", "", ""
                body = parts[1].strip()
                kr_idx = -1
                for idx, ch in enumerate(body):
                    if "가" <= ch <= "힣":
                        kr_idx = idx
                        break
                if kr_idx != -1:
                    cur_en = body[:kr_idx].replace("=", "").strip()
                    cur_kr = body[kr_idx:].strip()
                else:
                    cur_en = body.replace("=", "").strip()
            else:
                has_kr = any("가" <= ch <= "힣" for ch in line)
                if cur_en and not cur_kr:
                    if has_kr:
                        cur_kr = line.strip()
                    elif not line.startswith("="):
                        cur_en += " " + line.replace("=", "").strip()
        if cur_en and cur_kr:
            items.append({"id": num, "korean": cur_kr, "english": cur_en, "note": cur_nt})
    except Exception as e:
        print("PDF 파싱 에러:", e)
    return items

# 현재 폴더 PDF 자동 로드
cur_dir = os.path.dirname(os.path.abspath(__file__))
for f in glob.glob(os.path.join(cur_dir, "*.pdf")):
    base = os.path.basename(f)
    for i in range(1, 21):
        k = str(i) + "강"
        if k in base:
            res = parse_pdf(f)
            if res:
                LECTURE_DB[k] = res

if not LECTURE_DB["1강"]:
    LECTURE_DB["1강"] = [{
        "id": 1,
        "korean": "그 소년은 아버지와 함께 집에 갔다.",
        "english": "The boy went home with his father.",
        "note": "명사구 주어 The boy + 과거형 동사 went"
    }]

def get_data(lec, idx):
    data = LECTURE_DB.get(lec, [])
    if not data:
        return 0, "(등록된 예문 없음)", "[0 / 0 문장]", "", "", "", "", "", None
    idx = max(0, min(idx, len(data) - 1))
    curr = data[idx]
    info = "[" + str(idx + 1) + " / " + str(len(data)) + " 문장]"
    return idx, curr["korean"], info, "", "", "", "", "", None

def audio_to_text(audio_path):
    if not audio_path:
        return ""
    r = sr.Recognizer()
    try:
        with sr.AudioFile(audio_path) as s:
            return r.recognize_google(r.record(s), language="en-US")
    except Exception:
        return "[음성 인식 실패: 다시 발음해 보세요]"

def text_to_speech(text):
    if not text:
        return None
    try:
        clean = text.replace("[", "").replace("]", "").replace("(", "").replace(")", "").strip()
        tts = gTTS(text=clean, lang="en", tld="com")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(tmp.name)
        return tmp.name
    except Exception as e:
        print("TTS 에러:", e)
        return None

def evaluate(lec, idx, audio, text):
    data = LECTURE_DB.get(lec, [])
    if not data or idx >= len(data):
        return "", "", "", "", None
    target = data[idx]
    user_val = audio_to_text(audio) if audio else text
    st = "비교 및 보완이 필요합니다."
    if user_val:
        u_clean = "".join(c for c in user_val.lower() if c.isalnum() or c.isspace()).strip()
        t_clean = "".join(c for c in target["english"].lower() if c.isalnum() or c.isspace()).strip()
        if u_clean == t_clean:
            st = "모범 답안과 정확히 일치합니다!"
    native_audio = text_to_speech(target["english"])
    return user_val, target["english"], target["note"], st, native_audio

def register_pdf(lec_key, uploaded_file):
    if not uploaded_file:
        return "업로드된 파일이 없습니다."
    fpath = uploaded_file.name if hasattr(uploaded_file, "name") else uploaded_file
    items = parse_pdf(fpath)
    if not items:
        return "[" + lec_key + "] PDF에서 문장을 추출하지 못했습니다."
    LECTURE_DB[lec_key] = items
    return "[" + lec_key + "] 총 " + str(len(items)) + "개 문장이 성공적으로 등록되었습니다!"

with gr.Blocks(title="파씨 스터디 영작문 실습") as demo:
    gr.Markdown("# 방송대 영문과 파씨 스터디: 영작문 실습 프로그램")
    idx_state = gr.State(value=0)

    with gr.Tab("학습 및 녹음"):
        with gr.Row():
            lec_sel = gr.Dropdown(
                label="강의 선택",
                choices=[str(i) + "강" for i in range(1, 21)],
                value="1강",
                scale=1
            )
            prog_v = gr.Textbox(
                label="진행 현황",
                value="[1 / " + str(len(LECTURE_DB["1강"])) + " 문장]",
                scale=1,
                interactive=False
            )

        kr_v = gr.Textbox(
            label="한글 제시문",
            value=LECTURE_DB["1강"][0]["korean"],
            interactive=False
        )

        with gr.Row():
            btn_prev = gr.Button("◀ 이전 문장", variant="secondary")
            btn_next = gr.Button("다음 문장 ▶", variant="primary")

        with gr.Row():
            mic_in = gr.Audio(sources=["microphone"], type="filepath", label="영어 발화 녹음 (마이크)")
            txt_in = gr.Textbox(label="영작문 직접 입력 (보조용)", placeholder="영어로 작성해 보세요...")

        btn_submit = gr.Button("정답 확인 및 원어민 발음 듣기", variant="stop")

        with gr.Row():
            stt_out = gr.Textbox(label="내 발화 인식 결과 (STT)", interactive=False)
            judge_out = gr.Textbox(label="일치 여부", interactive=False)

        with gr.Row():
            ans_out = gr.Textbox(label="모범 답안", scale=3, interactive=False)
            audio_out = gr.Audio(label="원어민 발음 (모범 답안 듣기)", autoplay=True, scale=2)

        note_out = gr.Textbox(label="문법 및 학습 포인트", interactive=False)

        outs = [idx_state, kr_v, prog_v, txt_in, stt_out, ans_out, note_out, judge_out, audio_out]
        lec_sel.change(fn=lambda l: get_data(l, 0), inputs=[lec_sel], outputs=outs)
        btn_prev.click(fn=lambda l, i: get_data(l, i - 1), inputs=[lec_sel, idx_state], outputs=outs)
        btn_next.click(fn=lambda l, i: get_data(l, i + 1), inputs=[lec_sel, idx_state], outputs=outs)
        btn_submit.click(
            fn=evaluate,
            inputs=[lec_sel, idx_state, mic_in, txt_in],
            outputs=[stt_out, ans_out, note_out, judge_out, audio_out]
        )

    with gr.Tab("예문 등록 (교안 PDF 업로드)"):
        gr.Markdown("### 1강 ~ 20강 교안 PDF 등록")
        with gr.Row():
            target_lec = gr.Dropdown(
                label="등록 대상 강의 선택",
                choices=[str(i) + "강" for i in range(1, 21)],
                value="3강"
            )
            file_in = gr.File(label="PDF 파일 업로드", file_types=[".pdf"])
        upload_b = gr.Button("선택한 강의에 PDF 등록하기", variant="secondary")
        status_view = gr.Textbox(label="등록 상태", interactive=False)
        upload_b.click(fn=register_pdf, inputs=[target_lec, file_in], outputs=[status_view])

import os

if __name__ == "__main__":
    # Render가 자동으로 지정하는 포트를 읽고, 없으면 7860 사용
    port = int(os.environ.get("PORT", 7860))
    demo.launch(share=True)