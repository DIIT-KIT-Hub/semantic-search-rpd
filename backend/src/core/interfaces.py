from abc import ABC, abstractmethod

from backend.src.core.models import Chunk, Document, SearchResult


class BaseParser(ABC):
    """Абстрактний клас для парсера, який визначає інтерфейс для обробки різних типів файлів."""
    @abstractmethod
    def parse(self, file, filename) -> str:
        """Метод для парсингу файлу. Повертає текстовий вміст файлу."""
        raise NotImplementedError("Subclasses must implement the parse method")
    
    @abstractmethod
    def extract_structure(self, file) -> dict:
        """Метод для видобування структури файлу."""
        raise NotImplementedError("Subclasses must implement the extract_structure method")


class BaseChunker(ABC):
    """Абстрактний клас для чанкеру, який визначає інтерфейс для розбиття тексту на чанки."""
    @abstractmethod
    def chunk(self, text: str, metadata: dict) -> list[Chunk]:
        """Метод для розбиття тексту на чанки. Повертає список об'єктів Chunk."""
        raise NotImplementedError("Subclasses must implement the chunk method")
    

class BaseEmbedder(ABC):
    """Абстрактний клас для ембеддера, який визначає інтерфейс для перетворення тексту в векторні представлення."""
    @abstractmethod
    def embed(self, text: list[str]) -> list[list[float]]:
        """Метод для перетворення тексту в векторні представлення. Повертає список векторів."""
        raise NotImplementedError("Subclasses must implement the embed method")
    
    @abstractmethod
    def dimension(self) -> int:
        """Метод для отримання розміру векторного представлення."""
        raise NotImplementedError("Subclasses must implement the dimension method")
    

class BaseVectorStore(ABC):
    """Абстрактний клас для векторного сховища, який визначає інтерфейс для збереження та пошуку векторних представлень."""
    @abstractmethod
    def add(self, chunks):
        """Метод для додавання чанків до векторного сховища."""
        raise NotImplementedError("Subclasses must implement the add method")
    
    @abstractmethod
    def search(self, query_emb, top_k, filter) -> list[SearchResult]:
        """Метод для пошуку векторних представлень."""
        raise NotImplementedError("Subclasses must implement the search method")
    
    @abstractmethod
    def delete(self, document_id):
        """Метод для видалення документу з векторного сховища."""
        raise NotImplementedError("Subclasses must implement the delete method")
    
    @abstractmethod
    def list_documents(self) -> list[Document]:
        """Метод для переліку всіх документів у векторному сховищі."""
        raise NotImplementedError("Subclasses must implement the list_documents method")
    
    @abstractmethod
    def get_document(self, document_id) -> Document:
        """Метод для отримання документу за його ID."""
        raise NotImplementedError("Subclasses must implement the get_document method")
    