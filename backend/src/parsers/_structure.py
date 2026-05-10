"""
Структурний аналіз блоків РПД (шар B парсера).

Цей модуль НЕ читає файли, він приймає вже витягнуті Block-об'єкти від
шару A (DocxParser._extract_blocks або PdfParser._extract_blocks) і будує
ієрархію секцій з топіками.

Ключові функції:
    score_heading(block)        наскільки блок схожий на заголовок (0..N балів)
    classify_table(table)       A / B / C (параграф / тематичний план / матриця)
    parse_topics_table(table)   парсить таблицю тематичного плану у Section[]
    build_sections(blocks)      головна функція, повертає список Section
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from parsers._blocks import Block

logger = logging.getLogger(__name__)


# ============================================================================
# Константи і регулярні вирази
# ============================================================================

RE_NUM_PREFIX = re.compile(r'^\s*\d+(\.\d+)*\.?\s+')
"""Числовий префікс заголовка: '1 ', '1.1 ', '1.1. ' тощо."""

RE_SECTION = re.compile(r'^\s*Розділ\s+\d+(\.\d+)*\s*\.?', re.IGNORECASE)
"""'Розділ N.' або 'Розділ N.M.' на початку рядка."""

RE_LO_CODE = re.compile(r'\bОРН[\s\-]?\d+\b', re.IGNORECASE)
"""Код очікуваного результату навчання: 'ОРН1', 'ОРН-1', 'ОРН 1'."""

RPD_SECTION_PHRASES: list[str] = [
    # Розділи 1-го рівня
    'місце навчальної дисципліни',
    'місце навчальної дисципліни в освітній програмі',
    'очікувані результати навчання',
    'очікувані результати навчання за навчальною дисципліною',
    'розподіл годин за видами',
    'розподіл годин за видами навчальної діяльності',
    'зміст навчальної дисципліни',
    'методи викладання та навчання',
    'методи та критерії оцінювання',
    'ресурсне забезпечення',
    'ресурсне забезпечення навчальної дисципліни',
    'узгодження результатів навчання',
    # Розділи 2-го рівня
    'мета навчальної дисципліни',
    'компетентності, формування яких',
    'програмні результати навчання',
    'міждисциплінарні зв',
    'методи поточного оцінювання',
    'методи семестрового оцінювання',
    'критерії семестрового та підсумкового',
    'засоби навчання',
    'інформаційне та навчально-методичне',
    'загальні відомості',
]

TOPIC_TABLE_KEYWORDS: list[str] = [
    'тема заняття', 'тема лекції', 'розділ', 'обсяг', 'годин', 'орн',
]

MATRIX_TABLE_KEYWORDS: list[str] = [
    'прн', 'мн', 'зн', 'кз', 'компетентн', 'програмні результат',
]

SUBCATEGORY_PREFIXES: tuple[str, ...] = (
    'Лекції:',
    'Лабораторні роботи:',
    'Практичні заняття:',
    'Самостійна робота:',
    'Семінарські заняття:',
)

HEADING_SCORE_THRESHOLD = 3
"""Параграф вважається заголовком при score >= цього порогу."""


# ============================================================================
# Перерахування і data classes
# ============================================================================

class TableKind(Enum):
    """Тип таблиці для подальшої обробки."""
    A = 'A'  # таблиця-параграф (просто текст у клітинках)
    B = 'B'  # тематичний план, парситься семантично у parse_topics_table
    C = 'C'  # допоміжна матриця (ОРН↔ПРН↔Методи), серіалізується як параграф


@dataclass
class Topic:
    """Один топік (тема заняття) з тематичного плану."""
    number: int
    title: str
    content: str
    hours: Optional[float] = None
    learning_outcomes: Optional[str] = None
    learning_outcomes_codes: list[str] = field(default_factory=list)
    soft_skills: Optional[str] = None
    page_number: Optional[int] = None  # для PDF, для DOCX = None


@dataclass
class Section:
    """Секція РПД (наприклад 'Розділ 1. Основи...' або '1.1 Мета')."""
    title: str
    level: int = 1
    content: str = ''
    topics: list[Topic] = field(default_factory=list)
    page_number: Optional[int] = None


# ============================================================================
# Розпізнавання заголовків
# ============================================================================

def matches_phrase(text: str) -> int:
    """
    Скільки балів дати за збіг з фразою-сигнатурою РПД.

    Returns:
        +2 точний збіг (з опційним числовим префіксом і опційною ':' або '.' в кінці)
        +1 фраза є префіксом, далі є продовження
         0 інакше
    """
    if not text:
        return 0
    t = text.lower().strip()
    t_clean = RE_NUM_PREFIX.sub('', t)
    t_clean = t_clean.rstrip('.: ').strip()

    for ph in RPD_SECTION_PHRASES:
        if t_clean == ph:
            return 2
        if t_clean.startswith(ph + ' ') or t_clean.startswith(ph + ','):
            return 1
    return 0


def score_heading(block: Block) -> int:
    """
    Обчислює оцінку, наскільки блок схожий на заголовок секції.

    Заголовок при score >= HEADING_SCORE_THRESHOLD (3).
    """
    if block.kind != 'paragraph' or not block.text.strip():
        return 0

    score = 0
    text = block.text.strip()

    # +3: явний стиль Heading 1/2/3
    if block.style_name and any(
        h in block.style_name.lower() for h in ('heading 1', 'heading 2', 'heading 3')
    ):
        score += 3

    # +2: числовий префікс '1 ', '1.1 ', '1.1.1 '
    if RE_NUM_PREFIX.match(text):
        score += 2

    # +2: UPPERCASE
    if block.is_uppercase:
        score += 2

    # +1: bold
    if block.is_bold:
        score += 1

    # +1..+2: фраза-сигнатура
    score += matches_phrase(text)

    # -2: занадто довгий, не заголовок
    if len(text) > 200:
        score -= 2

    # -1: починається з малої літери
    if text[0].islower():
        score -= 1

    # -1: закінчується на , або . або : (заголовки рідко такі)
    if text.endswith((',', '.', ':')):
        score -= 1

    return score


def detect_heading_level(block: Block) -> int:
    """
    Повертає рівень заголовка 1 / 2 / 3 на основі числового префіксу і стилю.

    Викликається лише після того, як score_heading() повернув >= порогу.
    """
    text = block.text.strip()
    m = RE_NUM_PREFIX.match(text)
    if m:
        prefix = m.group().strip().rstrip('.')
        depth = prefix.count('.') + 1
        return min(depth, 3)

    # Без числового префіксу: UPPERCASE → level 1, інакше level 2
    if block.is_uppercase:
        return 1
    if block.style_name:
        s = block.style_name.lower()
        if 'heading 1' in s:
            return 1
        if 'heading 2' in s:
            return 2
        if 'heading 3' in s:
            return 3
    return 2


# ============================================================================
# Класифікація таблиць
# ============================================================================

def classify_table(table: list[list[str]]) -> TableKind:
    """
    Визначає тип таблиці за шапкою (першим рядком).

    Returns:
        TableKind.B тематичний план (≥ 2 ключових слова + ≥ 5 рядків)
        TableKind.C допоміжна матриця (≥ 2 matrix-ключових слова)
        TableKind.A все інше (звичайна таблиця-параграф)
    """
    if not table or len(table) < 2:
        return TableKind.A

    header_text = ' '.join((c or '').lower() for c in table[0])

    # Тематичний план
    topic_hits = sum(1 for kw in TOPIC_TABLE_KEYWORDS if kw in header_text)
    if topic_hits >= 2 and len(table) >= 5:
        return TableKind.B

    # Допоміжна матриця
    matrix_hits = sum(1 for kw in MATRIX_TABLE_KEYWORDS if kw in header_text)
    if matrix_hits >= 2:
        return TableKind.C

    return TableKind.A


# ============================================================================
# Парсинг тематичного плану
# ============================================================================

def identify_columns(header: list[str]) -> dict[str, int]:
    """
    Будує мапу 'семантична роль колонки → фізичний індекс' за шапкою таблиці.

    Це КЛЮЧОВА абстракція. Різні РПД мають різну розкладку колонок:
        Приклад 1: ['Тема заняття', 'Обсяг годин', 'ОРН', 'СН']
        Приклад 2: ['Розділ', 'Розділ', 'Тема заняття', ..., 'ОРН', 'ОРН', 'СН']
        Приклад 3: ['Розділ', 'Тема заняття', 'Обсяг, годин', '', 'ОРН', 'СН']

    Замість того, щоб у решті коду писати row[1] для годин, тут читаємо ШАПКУ і повертаємо словник, через який далі звертаємось: row[cols['hours']].

    Returns:
        dict з ключами 'topic', 'hours', 'orn', 'sn', 'section_no'
        присутні лише ті, які реально знайшлися. 'topic' гарантовано є
        (fallback на колонку 0).
    """
    cols: dict[str, int] = {}
    for i, raw in enumerate(header):
        if not raw:
            continue
        cell = raw.lower().strip()

        # Розділ - окрема колонка (НЕ topic). Часто стоїть першою.
        if 'section_no' not in cols and cell == 'розділ':
            cols['section_no'] = i

        # Тема заняття / Тема лекції пріоритетна колонка для topic.
        if 'topic' not in cols and 'тема' in cell:
            cols['topic'] = i

        # Обсяг / години.
        if 'hours' not in cols and ('обсяг' in cell or 'годин' in cell):
            cols['hours'] = i

        # ОРН, очікувані результати навчання.
        if 'orn' not in cols and 'орн' in cell:
            cols['orn'] = i

        # СН, соціальні навички (soft skills).
        if 'sn' not in cols and (cell == 'сн' or 'соціальн' in cell or 'soft skills' in cell):
            cols['sn'] = i

    # fallback: topic колонка 0 (якщо нічого не зматчилось).
    cols.setdefault('topic', 0)
    return cols


def parse_hours(row: list[str], cols: dict[str, int]) -> Optional[float]:
    """
    Витягує кількість годин з клітинки.
      ''     → None
      '4'    → 4.0
      '0,5'  → 0.5
      '—'    → None
      'abc'  → None
    """
    if 'hours' not in cols or cols['hours'] >= len(row):
        return None
    raw = (row[cols['hours']] or '').strip()
    if not raw or raw in ('-', '–', '—'):
        return None
    raw = raw.replace(',', '.').replace(' ', '')
    try:
        return float(raw)
    except ValueError:
        logger.debug("parse_hours: non-numeric value %r → None", raw)
        return None


def parse_learning_outcomes(raw: Optional[str]) -> tuple[Optional[str], list[str]]:
    """
    Парсить клітинку ОРН.

    Args:
        raw: сирий текст клітинки, наприклад 'ОРН1\\nОРН3\\nОРН9' або 'ОРН1-ОРН4'.

    Returns:
        (оригінальний_текст, список_нормалізованих_кодів)
        Приклад: ('ОРН1\\nОРН3', ['ОРН1', 'ОРН3'])
    """
    if not raw or not raw.strip():
        return None, []
    text = raw.strip()
    codes = [
        m.group(0).upper().replace(' ', '').replace('-', '')
        for m in RE_LO_CODE.finditer(text)
    ]
    # Унікальні і відсортовані
    return text, sorted(set(codes))


def _ensure_section(sections: list[Section], current: Optional[Section]) -> Section:
    """Повертає поточну section або створює, якщо немає."""
    if current is None:
        current = Section(title='Тематичний план', level=1, topics=[])
        sections.append(current)
    return current


def add_topic(
    topic_number: int,
    topic_title: str,
    current_subcategory: Optional[str],
    row: list[str],
    cols: dict[str, int],
    page_number: Optional[int] = None,
) -> Topic:
    """Створює об'єкт Topic з рядка таблиці."""
    raw_lo: Optional[str] = None
    if 'orn' in cols and cols['orn'] < len(row):
        raw_lo = row[cols['orn']]
    lo_text, lo_codes = parse_learning_outcomes(raw_lo)

    raw_sn: Optional[str] = None
    if 'sn' in cols and cols['sn'] < len(row):
        raw_sn = row[cols['sn']]

    content = topic_title
    if current_subcategory:
        content = f'{current_subcategory}. {topic_title}'

    return Topic(
        number=topic_number,
        title=topic_title.strip(),
        content=content.strip(),
        hours=parse_hours(row, cols),
        learning_outcomes=lo_text,
        learning_outcomes_codes=lo_codes,
        soft_skills=raw_sn.strip() if raw_sn else None,
        page_number=page_number,
    )


def parse_topics_table(
    table: list[list[str]],
    page_number: Optional[int] = None,
) -> list[Section]:
    """
    Парсить таблицю тематичного плану у список Section з вкладеними Topic.

    Розпізнає три типи рядків:
      1. Рядок-розділ - всі непорожні клітинки однакові і починаються
         з 'Розділ N.'. Створює нову Section.
      2. Рядок-підкатегорія - перша клітинка стартує з 'Лекції:',
         'Лабораторні роботи:', 'Практичні заняття:', 'Самостійна робота:'.
         Перемикає current_subcategory. 
         Якщо в тій же клітинці після переносу йде перша тема, додає її як топік.
      3. Звичайна тема - будь-який інший рядок з непорожньою першою клітинкою.
    """
    sections: list[Section] = []
    if not table or len(table) < 2:
        return sections

    cols = identify_columns(table[0])
    current_section: Optional[Section] = None
    current_subcategory: Optional[str] = None
    topic_number = 0

    for row in table[1:]:
        # 1) Рядок-розділ
        unique_cells = {(c or '').strip() for c in row if (c or '').strip()}
        if len(unique_cells) == 1:
            (text,) = unique_cells
            if RE_SECTION.match(text):
                current_section = Section(
                    title=text, level=1, topics=[], page_number=page_number,
                )
                sections.append(current_section)
                topic_number = 0
                current_subcategory = None
                continue

        # 2) Рядок-підкатегорія
        topic_idx = cols['topic']
        if topic_idx >= len(row):
            continue
        first_cell = (row[topic_idx] or '').strip()
        if not first_cell:
            continue

        matched_subcategory = False
        for kw in SUBCATEGORY_PREFIXES:
            if first_cell.startswith(kw):
                current_subcategory = kw.rstrip(':')
                # Інколи у тій же клітинці після переносу перша тема:
                # 'Лекції:\nExt JS' → підкатегорія 'Лекції' + тема 'Ext JS'.
                rest = first_cell[len(kw):].strip().lstrip('\n').strip()
                if rest:
                    current_section = _ensure_section(sections, current_section)
                    topic_number += 1
                    current_section.topics.append(
                        add_topic(topic_number, rest, current_subcategory, row, cols, page_number)
                    )
                matched_subcategory = True
                break
        if matched_subcategory:
            continue

        # 3) Звичайна тема
        current_section = _ensure_section(sections, current_section)
        topic_number += 1
        current_section.topics.append(
            add_topic(topic_number, first_cell, current_subcategory, row, cols, page_number)
        )

    return sections


# ============================================================================
# Головна функція шару B
# ============================================================================

def build_sections(blocks: list[Block]) -> list[Section]:
    """
    Будує ієрархію секцій з блоків. Тришаровий fallback:

      Етап 1: Normal flow - є ≥ 3 заголовків у тексті (score_heading >= 3).
              Кожен заголовок створює Section, текст між ним і наступним
              заголовком її content. Таблиці типу B всередині content
              додають свої topics у відповідну Section.

      Етап 2: Degraded - заголовків < 3, але є таблиця тематичного плану.
              Використовуємо її (parse_topics_table).

      Етап 3: Full fallback - нічого не знайшлось. Повертаємо одну Section
              з усім текстом.
    """
    # Знаходимо всі ймовірні заголовки
    headings: list[tuple[int, Block, int]] = []  # (block_index, block, score)
    for i, b in enumerate(blocks):
        if b.kind != 'paragraph':
            continue
        s = score_heading(b)
        if s >= HEADING_SCORE_THRESHOLD:
            headings.append((i, b, s))

    # Знаходимо всі таблиці тематичного плану
    topic_tables: list[Block] = []
    for b in blocks:
        if b.kind == 'table' and b.raw_table:
            if classify_table(b.raw_table) == TableKind.B:
                topic_tables.append(b)

    # === Етап 1: Normal flow ===
    if len(headings) >= 3:
        return _build_from_headings(blocks, headings, topic_tables)

    # === Етап 2: Degraded ===
    if topic_tables:
        logger.warning("build_sections: < 3 headings, falling back to topic-tables-only mode")
        sections: list[Section] = []
        for tb in topic_tables:
            if tb.raw_table:
                sections.extend(parse_topics_table(tb.raw_table, page_number=tb.page_number))
        if sections:
            return sections

    # === Етап 3: Full fallback ===
    logger.warning("build_sections: no detectable structure, using flat fallback")
    all_text = '\n\n'.join(b.text for b in blocks if b.text.strip())
    return [Section(title='Документ', level=1, content=all_text)]


def _build_from_headings(
    blocks: list[Block],
    headings: list[tuple[int, Block, int]],
    topic_tables: list[Block],
) -> list[Section]:
    """Будує секції за знайденими заголовками. Викликається з build_sections()."""
    sections: list[Section] = []
    heading_indices = [idx for idx, _, _ in headings]

    for n, (h_idx, h_block, _score) in enumerate(headings):
        next_idx = heading_indices[n + 1] if n + 1 < len(heading_indices) else len(blocks)

        # Текст між цим заголовком і наступним.
        body_blocks = blocks[h_idx + 1:next_idx]
        content = '\n\n'.join(b.text for b in body_blocks if b.kind == 'paragraph' and b.text.strip())

        # Таблиці типу B всередині цього інтервалу, додаємо topics у section.
        topics: list[Topic] = []
        for b in body_blocks:
            if b.kind == 'table' and b.raw_table and classify_table(b.raw_table) == TableKind.B:
                for sub in parse_topics_table(b.raw_table, page_number=b.page_number):
                    topics.extend(sub.topics)

        sections.append(Section(
            title=h_block.text.strip(),
            level=detect_heading_level(h_block),
            content=content,
            topics=topics,
            page_number=h_block.page_number,
        ))

    return sections
