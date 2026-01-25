from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status, Query, Path
from fastapi.responses import FileResponse
import os
from typing import Any, List
from sqlalchemy.orm import Session

from app.config import settings
from app.models.schemas import PDFExtractResponse, ErrorResponse, PDFDocumentListResponse, PDFDocumentResponse
from app.services.pdf_service import PDFService
from app.utils.file_utils import save_upload_file
from app.database.connection import get_db
from app.database.repository import PDFRepository

# Create router
router = APIRouter(tags=["PDF Operations"])


@router.post(
    "/extract",
    response_model=PDFExtractResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Extract content from a PDF file",
    description="Upload a PDF file and extract text, tables, and images. Optionally generates an LLM-powered summary."
)
async def extract_pdf(
        file: UploadFile = File(...),
        include_summary: bool = Query(
            True,
            description="Generate an LLM-powered summary of the document"
        ),
        db: Session = Depends(get_db)
) -> Any:
    """
    Extract content from a PDF file.

    Args:
        file (UploadFile): The PDF file to extract from
        include_summary (bool): Whether to generate LLM summary
        db (Session): Database session

    Returns:
        PDFExtractResponse: Extracted text, tables, and image links with document ID
    """
    # Validate file extension
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported."
        )

    try:
        # Save the uploaded file
        file_info = await save_upload_file(file)

        # Process the PDF
        result = await PDFService.process_pdf(db, file_info, include_summary=include_summary)

        # Ensure we have the document ID in the response
        if not result.id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate document ID"
            )

        # Debug: Print the response data
        print(f"Extract response: ID={result.id}, Filename={result.filename}")
        print(f"Extract response contains {len(result.images)} images")
        print(f"Summary included: {result.summary is not None}")

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing PDF: {str(e)}"
        )


@router.get(
    "/documents/{document_id}",
    response_model=PDFExtractResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get processed PDF by ID",
    description="Retrieve a previously processed PDF document by its ID."
)
async def get_pdf_document(
        document_id: str = Path(..., description="ID of the processed document"),
        db: Session = Depends(get_db)
) -> Any:
    """
    Get a processed PDF document by ID.

    Args:
        document_id (str): ID of the processed document
        db (Session): Database session

    Returns:
        PDFExtractResponse: Processed PDF data
    """
    result = await PDFService.get_pdf_by_id(db, document_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )

    return result


@router.get(
    "/documents",
    response_model=PDFDocumentListResponse,
    summary="List all processed PDF documents",
    description="Retrieve a list of all processed PDF documents with pagination."
)
async def list_pdf_documents(
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
        db: Session = Depends(get_db)
) -> Any:
    """
    List all processed PDF documents.

    Args:
        skip (int): Number of records to skip
        limit (int): Maximum number of records to return
        db (Session): Database session

    Returns:
        PDFDocumentListResponse: List of processed PDF documents
    """
    documents = PDFRepository.list_documents(db, skip=skip, limit=limit)
    total = len(PDFRepository.list_documents(db))

    # Convert to Pydantic models
    processed_documents = []
    for doc in documents:
        # Convert image models to image responses with URLs
        image_responses = []
        for img in doc.images:
            image_responses.append({
                "id": img.id,
                "page_number": img.page_number,
                "image_index": img.image_index,
                "filename": img.filename,
                "created_at": img.created_at,
                "url": f"{settings.API_PREFIX}/images/{img.filename}"
            })

        # Convert text content models
        text_contents = []
        for text in doc.text_contents:
            text_contents.append({
                "id": text.id,
                "page_number": text.page_number,
                "content": text.content,
                "created_at": text.created_at
            })

        # Convert table models
        tables = []
        for table in doc.tables:
            tables.append({
                "id": table.id,
                "page_number": table.page_number,
                "table_index": table.table_index,
                "table_data": table.table_data,
                "created_at": table.created_at
            })

        # Add processed document
        processed_documents.append({
            "id": doc.id,
            "filename": doc.filename,
            "original_filename": doc.original_filename,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
            "images": image_responses,
            "text_contents": text_contents,
            "tables": tables
        })

    return PDFDocumentListResponse(
        documents=processed_documents,
        total=total,
        skip=skip,
        limit=limit
    )


@router.get(
    "/debug/generate-uuid",
    summary="Debug endpoint - Generate a UUID",
    description="Generate a UUID to verify UUID generation is working correctly."
)
async def debug_generate_uuid():
    """
    Debug endpoint to generate and return a UUID.

    Returns:
        dict: A dictionary containing a generated UUID
    """
    from app.database.models import generate_uuid

    return {"generated_uuid": generate_uuid()}


@router.get(
    "/images/{filename}",
    summary="Download an extracted image",
    description="Download an image that was extracted from a PDF."
)
async def download_image(filename: str) -> Any:
    """
    Download an image that was extracted from a PDF.

    Args:
        filename (str): The image filename

    Returns:
        FileResponse: The image file
    """
    file_path = os.path.join(settings.IMAGE_FOLDER, filename)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image not found: {filename}"
        )

    return FileResponse(file_path)