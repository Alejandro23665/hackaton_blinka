# Importar todos los modelos aquí para que Alembic los vea en SQLModel.metadata
from app.models.document import Document, DocumentRegion
from app.models.page import Page, PageClassification
from app.models.processing import ExtractedField, ProcessingRun, RunIssue, RunStep
from app.models.stored_file import StoredFile
from app.models.submission import Submission, SubmissionFile

__all__ = [
    "Document",
    "DocumentRegion",
    "ExtractedField",
    "Page",
    "PageClassification",
    "ProcessingRun",
    "RunIssue",
    "RunStep",
    "StoredFile",
    "Submission",
    "SubmissionFile",
]
