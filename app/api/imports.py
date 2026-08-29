from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.auth import get_current_user
from app.importers.canonical import CanonicalItem
from app.importers.markdown import MarkdownImporter
from app.importers.source_factory import create_markdown_source
from app.models.user import User


router = APIRouter(
    prefix="/imports",
    tags=["imports"],
)


@router.post(
    "/markdown",
    response_model=list[CanonicalItem],
)
async def import_markdown(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
) -> list[CanonicalItem]:
    content = await file.read()

    source = create_markdown_source(
        content=content,
        filename=file.filename,
        title=title,
    )

    return MarkdownImporter().import_data(source)
