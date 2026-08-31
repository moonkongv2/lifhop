from pydantic import BaseModel


class ImportArtifactDownloadResponse(BaseModel):
    download_url: str
