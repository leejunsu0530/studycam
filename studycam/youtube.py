"""Optional YouTube OAuth login and daily-video upload support."""

from __future__ import annotations

from pathlib import Path

SCOPE = "https://www.googleapis.com/auth/youtube.upload"


class YouTubeSetupError(RuntimeError):
    pass


def _imports():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        return Request, Credentials, InstalledAppFlow, build, MediaFileUpload
    except ImportError as error:
        raise YouTubeSetupError("YouTube 기능을 쓰려면 `pip install .[youtube]`가 필요합니다.") from error


def authorize(client_secret: Path, token_path: Path) -> None:
    """Open the system browser and save the user's refresh token locally."""
    Request, Credentials, InstalledAppFlow, _, _ = _imports()
    credentials = None
    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(str(token_path), [SCOPE])
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    elif not credentials or not credentials.valid:
        if not client_secret.exists():
            raise YouTubeSetupError("Google OAuth client_secret JSON 파일을 먼저 선택하세요.")
        credentials = InstalledAppFlow.from_client_secrets_file(str(client_secret), [SCOPE]).run_local_server(port=0)
    token_path.write_text(credentials.to_json(), encoding="utf-8")


def upload(video: Path, token_path: Path, title: str, privacy: str) -> str:
    """Upload one MP4 and return the YouTube video ID."""
    Request, Credentials, _, build, MediaFileUpload = _imports()
    if not token_path.exists():
        raise YouTubeSetupError("YouTube 로그인이 필요합니다.")
    credentials = Credentials.from_authorized_user_file(str(token_path), [SCOPE])
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request()); token_path.write_text(credentials.to_json(), encoding="utf-8")
    if not credentials.valid:
        raise YouTubeSetupError("YouTube 로그인이 만료되었습니다. 설정에서 다시 로그인하세요.")
    service = build("youtube", "v3", credentials=credentials)
    request = service.videos().insert(
        part="snippet,status",
        body={"snippet": {"title": title, "description": "Created with StudyCam"}, "status": {"privacyStatus": privacy}},
        media_body=MediaFileUpload(str(video), mimetype="video/mp4", resumable=True),
    )
    response = request.execute()
    return response["id"]
