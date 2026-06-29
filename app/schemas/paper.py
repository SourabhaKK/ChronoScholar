from pydantic import BaseModel


class Paper(BaseModel):
    ...


class PaperIngestRequest(BaseModel):
    ...


class IngestResponse(BaseModel):
    ...
