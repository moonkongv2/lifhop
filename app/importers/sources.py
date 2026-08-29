from pydantic import BaseModel

# PlainTextSource
# - 사용자가 직접 붙여넣거나 입력한 텍스트

# MarkdownSource
# - .md 파일에서 읽어온 내용
# - 또는 Markdown 문자열


class PlainTextSource(BaseModel):
    content: str
    title: str | None = None


class MarkdownSource(BaseModel):
    content: str
    filename: str | None = None
    title: str | None = None
