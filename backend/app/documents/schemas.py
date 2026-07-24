from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version_number: int
    storage_path: str
    file_size: int
    file_checksum: str
    extraction_status: str
    created_at: datetime


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    created_by_user_id: str
    title: str
    original_filename: str
    content_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    latest_version: DocumentVersionResponse