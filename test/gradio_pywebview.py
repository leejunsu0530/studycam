"""
실험의 목적: 
1. gradio를 일반 웹 브라우저보다 메모리 등을 적게 차지하는 웹뷰에서 연다
2. 해당 웹뷰를 닫으면 gradio도 끝낸다
3. 동적 ui를 통해 유튜브를 불러온다

결과: 크롬창보다 3배쯤 빨리 동적 웹이 반응함
목적도 모두 성공함

embed/id 꼴의 url이 아니라 쌩 url을 넣으면, 임베딩되는 게 아니라 링크가 생겨버림

id 추출 방법은 알아서 잘 하면 되고(어처피 나중에 필요하니까),
ui와 나머지 단계가 서로 준비되면 열리게 하는 등의 안전장치도 나중에
"""
import re
import sys

import gradio as gr
import webview


def youtube_embed(url: str):

    if not url:
        return "<p>유튜브 URL을 입력하세요.</p>"

    patterns = [
        r"(?:youtube\.com/watch\?v=)([\w-]+)",
        r"(?:youtu\.be/)([\w-]+)",
        r"(?:youtube\.com/shorts/)([\w-]+)",
    ]

    video_id = None

    for pattern in patterns:
        match = re.search(pattern, url)

        if match:
            video_id = match.group(1)
            break

    if not video_id:
        return "<p>올바른 YouTube URL이 아닙니다.</p>"

    return f"""
    <div style="width: 100%; max-width: 1000px; margin: auto;">
        <iframe
            width="100%"
            height="562"
            src="https://www.youtube.com/embed/{video_id}"
            title="YouTube video player"
            frameborder="0"
            allowfullscreen>
        </iframe>
    </div>
    """


# ==================================
# 1. Gradio UI
# ==================================

with gr.Blocks(title="YouTube Viewer") as demo:

    gr.Markdown("# YouTube Viewer")

    url = gr.Textbox(
        label="YouTube URL",
        placeholder="https://www.youtube.com/watch?v=..."
    )

    load_button = gr.Button("불러오기")

    video = gr.HTML(
        value="<p>유튜브 URL을 입력하고 버튼을 누르세요.</p>"
    )

    load_button.click(
        youtube_embed,
        inputs=url,
        outputs=video
    )


# ==================================
# 2. Gradio 서버 시작
# ==================================

demo.launch(
    server_name="127.0.0.1",
    server_port=7860,
    prevent_thread_lock=True,
    inbrowser=False,
)


# ==================================
# 3. pywebview
# ==================================

window = webview.create_window(
    "YouTube Viewer",
    "http://127.0.0.1:7860",
    width=1200,
    height=800,
)


# ==================================
# 4. 창이 닫힐 때
# ==================================

def on_closed():
    print("WebView 창이 닫혔습니다.")

    # Gradio 서버 종료
    demo.close()

    # Python 프로그램 종료
    sys.exit(0)


window.events.closed += on_closed


# ==================================
# 5. WebView 실행
# ==================================

webview.start()
