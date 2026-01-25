import fitz  # PyMuPDF
import pdfplumber
import io
import os
import logging
from PIL import Image as PILImage
from typing import Dict, List, Tuple, Any, Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.models.schemas import TextData, TableData, ImageLink, FileInfo, PDFExtractResponse
from app.utils.file_utils import get_image_url
from app.database.repository import PDFRepository
from app.database.models import PDFDocument
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class PDFService:
    """Service for handling PDF operations."""

    @staticmethod
    async def extract_text_and_images(file_info: FileInfo, document_id: str) -> Tuple[TextData, List[ImageLink]]:
        """
        Extract text and images from a PDF file.

        Args:
            file_info (FileInfo): Information about the PDF file
            document_id (str): ID of the document in the database

        Returns:
            Tuple[TextData, List[ImageLink]]: Extracted text and image links
        """
        doc = fitz.open(file_info.path)
        text_data = {}
        image_links = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text_data[f"Page {page_num + 1}"] = page.get_text()

            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                image = PILImage.open(io.BytesIO(image_bytes))

                # Include document_id in the filename
                image_filename = f"{document_id}_page_{page_num + 1}_image_{img_index + 1}.{image_ext}"
                image_path = os.path.join(settings.IMAGE_FOLDER, image_filename)
                image.save(image_path)

                image_links.append(
                    ImageLink(
                        url=get_image_url(image_filename),
                        page=page_num + 1,
                        index=img_index + 1,
                        filename=image_filename,
                        document_id=document_id
                    )
                )

        doc.close()
        return TextData(pages=text_data), image_links

    @staticmethod
    async def extract_tables(file_info: FileInfo) -> TableData:
        """
        Extract tables from a PDF file.

        Args:
            file_info (FileInfo): Information about the PDF file

        Returns:
            TableData: Extracted table data
        """
        tables = {}

        with pdfplumber.open(file_info.path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                extracted_tables = page.extract_tables()
                if extracted_tables:
                    tables[f"Page {page_num + 1}"] = extracted_tables

        return TableData(pages=tables)

    @classmethod
    async def process_pdf(
        cls,
        db: Session,
        file_info: FileInfo,
        include_summary: bool = True
    ) -> PDFExtractResponse:
        """
        Process a PDF file to extract text, tables, and images.

        Args:
            db (Session): Database session
            file_info (FileInfo): Information about the PDF file
            include_summary (bool): Whether to generate LLM summary

        Returns:
            PDFExtractResponse: Processed PDF data with database IDs
        """
        # Create document in database
        document = PDFRepository.create_document(db, file_info)
        document_id = document.id

        # Extract data from PDF
        text_data, image_links = await cls.extract_text_and_images(file_info, document_id)
        table_data = await cls.extract_tables(file_info)

        # Save extracted data to database
        PDFRepository.save_text_content(db, document_id, text_data.pages)
        PDFRepository.save_images(db, document_id, [img.dict() for img in image_links])

        if table_data.pages:
            PDFRepository.save_tables(db, document_id, table_data.pages)

        # Generate LLM summary if requested
        summary = None
        if include_summary:
            summary = await cls.generate_summary(text_data)

        # Return response model
        return PDFExtractResponse(
            id=document_id,
            filename=file_info.filename,
            text=text_data,
            tables=table_data,
            images=image_links,
            summary=summary,
            created_at=document.created_at
        )

    @classmethod
    async def generate_summary(cls, text_data: TextData) -> Optional[str]:
        """
        Generate an LLM summary from extracted text data.

        Args:
            text_data: The extracted text data from the PDF

        Returns:
            Summary string or None if generation fails
        """
        try:
            # Combine all page text into a single document
            full_text = "\n\n".join(
                f"{page_name}:\n{content}"
                for page_name, content in text_data.pages.items()
            )

            if not full_text.strip():
                logger.warning("No text content available for summarization")
                return None

            summary = await LLMService.summarize_text(full_text)
            return summary

        except Exception as e:
            logger.error(f"Error generating PDF summary: {str(e)}")
            return None

    @classmethod
    async def get_pdf_by_id(cls, db: Session, document_id: str) -> PDFExtractResponse:
        """
        Get processed PDF data by document ID.

        Args:
            db (Session): Database session
            document_id (str): Document ID

        Returns:
            PDFExtractResponse: Processed PDF data
        """
        # Get document with all relations
        document = PDFRepository.get_document_with_relations(db, document_id)

        if not document:
            return None

        # Reconstruct text data
        text_pages = {}
        for text in document.text_contents:
            text_pages[f"Page {text.page_number}"] = text.content

        # Reconstruct tables data
        table_pages = {}
        for table in document.tables:
            page_key = f"Page {table.page_number}"
            if page_key not in table_pages:
                table_pages[page_key] = []

            import json
            table_data = json.loads(table.table_data)
            table_pages[page_key].append(table_data)

        # Reconstruct image links
        image_links = []
        for img in document.images:
            image_links.append(
                ImageLink(
                    url=get_image_url(img.filename),
                    page=img.page_number,
                    index=img.image_index,
                    filename=img.filename,
                    document_id=document_id
                )
            )

        # Return response model
        return PDFExtractResponse(
            id=document_id,
            filename=document.original_filename,
            text=TextData(pages=text_pages),
            tables=TableData(pages=table_pages),
            images=image_links,
            summary=None,  # Summary is not stored, regenerate if needed
            created_at=document.created_at
        )