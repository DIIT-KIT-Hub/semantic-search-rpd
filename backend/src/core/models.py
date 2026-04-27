from enum import Enum
from pydantic import BaseModel, Field
from uuid import uuid4
from typing import Optional
from datetime import datetime


class DocumentType(Enum):
    """Перелік типів файлів, які підтримуємо."""

    DOCX = "docx"
    PDF = "pdf"


class DocumentStatus(Enum):
    """Стан життєвого циклу документа."""

    UPLOADED = "uploaded"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


class ChunkMetadata(BaseModel):
    """Все, що зберігаємо про походження chunk'а."""

    document_id: str = Field(description="ID документа, з якого витягнуто цей chunk", examples=["123e4567-e89b-12d3-a456-426614174000"])
    document_name: str = Field(description="Назва документа", examples=["Лекція 1"])
    discipline_name: Optional[str] = Field(description="Назва дисципліни", examples=["Математика"])
    section: Optional[str] = Field(description="Розділ", examples=["1.1"])
    topic_number: Optional[int] = Field(description="Номер теми", examples=[1])
    topic_title: Optional[str] = Field(description="Назва теми", examples=["Основи математики"])
    chunk_index: int = Field(description="Індекс chunk'а", examples=[0])
    page_number: Optional[int] = Field(description="Номер сторінки", examples=[1])


class Chunk(BaseModel):
    """Фрагмент документа, готовий до індексації."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Унікальний ідентифікатор chunk'а", examples=["123e4567-e89b-12d3-a456-426614174000"])
    text: str = Field(description="Текст chunk'а", examples=["Це текст фрагмента документа."])
    metadata: ChunkMetadata = Field(description="Метадані chunk'а")
    embedding: Optional[list[float]] = Field(default = None, description="Вектор-репрезентація chunk'а", examples=[[0.1, 0.2, 0.3]])


class Document(BaseModel):
    """Метадані документа."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Унікальний ідентифікатор документа", examples=["123e4567-e89b-12d3-a456-426614174000"])
    filename: str = Field(description="Назва файлу, який завантажили", examples=["lecture1.pdf"])
    document_type: DocumentType = Field(description="Тип файлу", examples=[DocumentType.PDF])
    discipline_name: Optional[str] = Field(description="Назва дисципліни, до якої належить документ", examples=["Математика"])
    uploaded_at: datetime = Field(description="Дата та час завантаження документа", examples=["2024-06-01T12:00:00Z"])
    status: DocumentStatus = Field(description="Стан документа", examples=[DocumentStatus.UPLOADED])
    chunk_count: int = Field(default = 0, description="Кількість chunk'ів", examples=[0])
    error_message: Optional[str] = Field(description="Повідомлення про помилку", examples=[None])


class SearchQuery(BaseModel):
    """Тіло POST-запиту /api/search."""

    query: str = Field(description="Текст запиту", examples=["що таке математика?"])
    top_k: int = Field(default=5, ge=1, le=50, description="Кількість результатів для повернення", examples=[5])
    filter_discipline: Optional[str] = Field(description="Фільтр за дисципліною", examples=["Математика"])


class SearchResult(BaseModel):
    """Один результат пошуку."""

    chunk_id: str = Field(description="ID chunk'а, який відповідає результату пошуку", examples=["123e4567-e89b-12d3-a456-426614174000"])
    text: str = Field(description="Текст chunk'а", examples=["Це текст фрагмента документа."])
    score: float = Field(ge=0.0, le=1.0, description="Оцінка відповідності", examples=[0.8])
    metadata: ChunkMetadata = Field(description="Метадані chunk'а")


class SearchResponse(BaseModel):
    """Тіло відповіді /api/search."""

    query: str = Field(description="Текст запиту", examples=["що таке математика?"])
    results: list[SearchResult] = Field(description="Список результатів пошуку")
    total_found: int = Field(description="Загальна кількість знайдених результатів", examples=[100])
    took_ms: int = Field(description="Час виконання запиту в мілісекундах", examples=[100])


class UploadResponse(BaseModel):
    """Тіло відповіді POST /api/documents/upload."""

    document_id: str = Field(description="ID завантаженого документа", examples=["123e4567-e89b-12d3-a456-426614174000"])
    filename: str = Field(description="Назва файлу", examples=["document.pdf"])
    status: DocumentStatus = Field(description="Статус завантаження", examples=[DocumentStatus.UPLOADED])
    message: str = Field(description="Повідомлення про статус завантаження", examples=["Документ успішно завантажено"])    


class HealthResponse(BaseModel):
    """Тіло відповіді GET /api/health."""

    status: str = Field(default = "ok", description="Статус системи", examples=["ok"])
    version: str = Field(description="Версія API", examples=["1.0.0"])
    embedder: str = Field(description="Тип embedder", examples=["sentence-transformers"])
    store: str = Field(description="Тип сховища", examples=["in-memory"])