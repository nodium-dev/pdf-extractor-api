from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime


class FileInfo(BaseModel):
    """Model for file information."""
    filename: str
    path: str


class TextData(BaseModel):
    """Model for text extracted from each page."""
    pages: Dict[str, str] = Field(description="Dictionary mapping page numbers to extracted text")


class TableData(BaseModel):
    """Model for tables extracted from each page."""
    pages: Dict[str, List[List[Any]]] = Field(description="Dictionary mapping page numbers to tables")


class ImageLink(BaseModel):
    """Model for an image link."""
    url: str = Field(description="URL to download the image")
    page: int = Field(description="Page number where the image appears")
    index: int = Field(description="Index of the image on the page")
    filename: str = Field(description="Filename of the saved image")
    document_id: str = Field(description="ID of the document this image belongs to")


class PDFExtractResponse(BaseModel):
    """Response model for PDF extraction."""
    id: str = Field(description="Unique ID of the processed document")
    filename: str = Field(description="Original filename of the document")
    text: TextData = Field(description="Extracted text data")
    tables: TableData = Field(description="Extracted table data")
    images: List[ImageLink] = Field(description="List of links to extracted images")
    summary: Optional[str] = Field(default=None, description="LLM-generated summary of the document")
    created_at: datetime = Field(description="When the document was processed")


class ErrorResponse(BaseModel):
    """Model for error responses."""
    detail: str = Field(description="Error description")


# Database response models
class TextContentBase(BaseModel):
    """Base model for text content."""
    page_number: int
    content: str


class TextContentCreate(TextContentBase):
    """Model for creating text content."""
    document_id: str


class TextContentResponse(TextContentBase):
    """Response model for text content."""
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


class ImageBase(BaseModel):
    """Base model for image."""
    page_number: int
    image_index: int
    filename: str


class ImageCreate(ImageBase):
    """Model for creating image."""
    document_id: str


class ImageResponse(ImageBase):
    """Response model for image."""
    id: str
    created_at: datetime
    url: str

    class Config:
        from_attributes = True


class TableBase(BaseModel):
    """Base model for table."""
    page_number: int
    table_index: int
    table_data: str  # JSON string


class TableCreate(TableBase):
    """Model for creating table."""
    document_id: str


class TableResponse(TableBase):
    """Response model for table."""
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


class PDFDocumentBase(BaseModel):
    """Base model for PDF document."""
    filename: str
    original_filename: str


class PDFDocumentCreate(PDFDocumentBase):
    """Model for creating PDF document."""
    pass


class PDFDocumentResponse(PDFDocumentBase):
    """Response model for PDF document."""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    text_contents: Optional[List[TextContentResponse]] = []
    images: Optional[List[ImageResponse]] = []
    tables: Optional[List[TableResponse]] = []

    model_config = {"from_attributes": True}


class PDFDocumentListResponse(BaseModel):
    """Response model for listing PDF documents."""
    documents: List[PDFDocumentResponse]
    total: int
    skip: int
    limit: int