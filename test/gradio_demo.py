"""https://gradio.app/guides/quickstart

instead of python.exe, use below
gradio gradio_demo.py"""
from run_gr_in_webview import demo_launch_in_webview

import gradio as gr  # 라이브러리 자체도 무겁나보네... 그래도 실제로 쓰기엔 나쁘지 않음


def greet(name, intensity):
    return "Hello, " + name + "?" * int(intensity)


print("라이브러리 로딩됨")

demo = gr.Interface(
    fn=greet,
    inputs=["text", "slider"],
    outputs=["text"],
    api_name="predict"
)

print("demo 완료")

demo_launch_in_webview(demo)
