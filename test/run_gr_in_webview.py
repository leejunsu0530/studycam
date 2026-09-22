"""
demo.launch()를 대신해서 사용하는 함수.

나중에 개조해서 내부로 포함?
"""
import sys
import webview
import gradio
from rich.console import Console
# 다른 로직은 create_window 뒤에 막혀서 스레드를 쓰라고 함...

__all__ = ['demo_launch_in_webview']


def demo_launch_in_webview(demo: gradio.Interface, console: None | Console = None) -> None:
    """demo.launch(prevent_thread_lock=True)
    이 옵션으로 구동할 필요가 있음. 

    아래는 정식으로 편입할 때 수정할 것.
    1. create_window 등에 다른 옵션들을 전달할 수 있게 해야 함
    2. window가 None일 때 이 스레드만 닫힌다거나 하는 문제가 생길 수 있음 > 테스트해보기
    3. window가 None일 때 그 원인과 발생 위치를 알려야 함
    4. 지금 구조대로면 demo를 키고는 그걸 끄면 꺼지니까, 이 함수가 무조건 제일 마지막에 실행되어야 한다는 문제가 있음.
    """
    if console is None:
        console = Console()

    with console.status("[green]Launching demo...", spinner='arrow3'):
        demo.launch(prevent_thread_lock=True)

    window = webview.create_window(
        "test",
        "http://127.0.0.1:7860",
        width=1200,
        height=800,
    )
    if window is None:
        print("[Warning] window가 None입니다. 웹뷰를 사용할 수 없습니다. 프로그램을 종료합니다.")
        sys.exit(1)  # 에러코드와 함께 종료

    def on_closed():
        print("WebView 창이 닫혔습니다.")

        with console.status("[green]Closing gradio and python...", spinner="material"):
            # 근데 이거 닫히고도 한참 기다리는데... 이건 다른 스레드 닫는건가?

            # Gradio 서버 종료
            demo.close()
            # Python 프로그램 종료
            sys.exit(0)

    window.events.closed += on_closed

    webview.start()


if __name__ == "__main__":
    def greet(name, intensity):
        return "Hello, " + name + "!" * int(intensity)

    demo_ = gradio.Interface(
        fn=greet,
        inputs=["text", "slider"],
        outputs=["text"],
        api_name="predict"
    )

    demo_launch_in_webview(demo_)
