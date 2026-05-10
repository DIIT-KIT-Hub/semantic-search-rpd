from typing import Literal

from attr import dataclass


@dataclass
class Block:
    """Універсальна структура для абзаців, таблиць та зображень. Використовується для уніфікації обробки різних типів контенту в DOCX та PDF."""
    kind: Literal['paragraph', 'table', 'image']
    text: str                                 # для paragraph — текст; для table — серіалізовані клітинки; для image — alt-текст або '' 
    raw_table: list[list[str]] | None = None  # для table — повна матриця клітинок
    page_number: int | None = None            # для PDF; для DOCX = None
    style_name: str | None = None             # 'Heading 1', 'Normal', тощо (DOCX); для PDF = None
    is_bold: bool = False
    is_uppercase: bool = False                # обчислюється у самому Block
    alignment: str | None = None              # 'center', 'left', 'right'
    block_index: int = 0                      # порядковий номер у документі
