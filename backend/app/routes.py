from app.llm import generate_grounded_answer,validate_source_ids
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
import os
import re
from difflib import SequenceMatcher
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.embeddings import embed_texts
from app.ingestion import chunk_text, extract_text
from app.models import Chunk, Document, DocumentVersion


router = APIRouter(prefix="/documents", tags=["Documents"])


class SearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)
    document_key: str | None = None
    as_of: date | None = None


class AnswerRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    document_key: str | None = None
    as_of: date | None = None
    top_k: int = Field(default=5, ge=1, le=10)

def utc_midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


@router.post("/upload", status_code=201)
def upload_document(
    title: str = Form(..., min_length=1, max_length=255),
    document_key: str = Form(..., min_length=1, max_length=255),
    version_label: str = Form(..., min_length=1, max_length=100),
    effective_from: date = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    filename = Path(file.filename or "").name

    try:
        content = file.file.read(10 * 1024 * 1024 + 1)
        text = extract_text(filename, content)
        chunks = chunk_text(text)

        if not chunks:
            raise ValueError("No text chunks were created")

        embeddings = embed_texts(chunks)

    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="Could not read PDF. Check that it is valid and not encrypted.",
            ) from exc
        raise HTTPException(
            status_code=500,
            detail="Document processing failed.",
        ) from exc

    key = document_key.strip()
    label = version_label.strip()
    clean_title = title.strip()

    if not key or not label or not clean_title:
        raise HTTPException(
            status_code=400,
            detail="Fields cannot be blank",
        )

    try:
        document = db.scalar(
            select(Document).where(Document.document_key == key)
        )

        if document is None:
            document = Document(
                title=clean_title,
                document_key=key,
            )
            db.add(document)
            db.flush()
        else:
            document.title = clean_title

        version = DocumentVersion(
            document_id=document.id,
            version_label=label,
            effective_from=utc_midnight(effective_from),
            status="draft",
            source_filename=filename,
        )
        db.add(version)
        db.flush()

        db.add_all(
            [
                Chunk(
                    version_id=version.id,
                    chunk_index=index,
                    content=chunk,
                    embedding=embeddings[index],
                )
                for index, chunk in enumerate(chunks)
            ]
        )

        db.commit()

        return {
            "document_id": document.id,
            "document_key": document.document_key,
            "version_id": version.id,
            "version_label": version.version_label,
            "effective_from": effective_from.isoformat(),
            "status": version.status,
            "filename": filename,
            "characters_extracted": len(text),
            "chunks_created": len(chunks),
            "message": "Document version ingested successfully",
        }

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This document version already exists or conflicts with existing metadata.",
        ) from exc
    except Exception:
        db.rollback()
        raise


@router.get("/{document_key}/versions")
def list_versions(
    document_key: str,
    db: Session = Depends(get_db),
):
    document = db.scalar(
        select(Document).where(Document.document_key == document_key)
    )

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    versions = db.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.effective_from)
    ).all()

    return {
        "document_key": document.document_key,
        "title": document.title,
        "versions": [
            {
                "version_label": version.version_label,
                "effective_from": version.effective_from.isoformat(),
                "effective_to": (
                    version.effective_to.isoformat()
                    if version.effective_to
                    else None
                ),
                "status": version.status,
                "source_filename": version.source_filename,
            }
            for version in versions
        ],
    }


@router.post("/{document_key}/versions/{version_label}/publish")
def publish_version(
    document_key: str,
    version_label: str,
    db: Session = Depends(get_db),
):
    document = db.scalar(
        select(Document)
        .where(Document.document_key == document_key)
        .with_for_update()
    )

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    versions = db.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.effective_from)
        .with_for_update()
    ).all()

    target = next(
        (v for v in versions if v.version_label == version_label),
        None,
    )

    if target is None:
        raise HTTPException(status_code=404, detail="Version not found")

    target_chunks = db.scalar(
        select(Chunk.id)
        .where(Chunk.version_id == target.id)
        .limit(1)
    )

    if target_chunks is None:
        raise HTTPException(
            status_code=409,
            detail="Cannot publish a version without chunks.",
        )

    published = [
        v for v in versions
        if v.status == "published" and v.id != target.id
    ]

    for existing in published:
        if existing.effective_from == target.effective_from:
            raise HTTPException(
                status_code=409,
                detail="Another published version has the same effective date.",
            )

    target.status = "published"

    timeline = sorted(
        [v for v in versions if v.status == "published"],
        key=lambda v: v.effective_from,
    )

    for index, version in enumerate(timeline):
        version.effective_to = (
            timeline[index + 1].effective_from
            if index + 1 < len(timeline)
            else None
        )

    db.commit()

    return {
        "document_key": document_key,
        "version_label": target.version_label,
        "status": target.status,
        "effective_from": target.effective_from.isoformat(),
        "effective_to": (
            target.effective_to.isoformat()
            if target.effective_to
            else None
        ),
        "message": "Version published and timeline recalculated.",
    }

@router.get("")
def list_documents(db: Session = Depends(get_db)):
    documents = db.scalars(
        select(Document).order_by(Document.title)
    ).all()

    return {
        "documents": [
            {
                "document_key": document.document_key,
                "title": document.title,
                "created_at": (
                    document.created_at.isoformat()
                    if document.created_at else None
                ),
                "versions": [
                    {
                        "version_label": version.version_label,
                        "effective_from": version.effective_from.isoformat(),
                        "effective_to": (
                            version.effective_to.isoformat()
                            if version.effective_to else None
                        ),
                        "status": version.status,
                        "source_filename": version.source_filename,
                    }
                    for version in sorted(
                        document.versions,
                        key=lambda v: v.effective_from,
                    )
                ],
            }
            for document in documents
        ]
    }

@router.post("/search")
def semantic_search(
    request: SearchRequest,
    db: Session = Depends(get_db),
):
    as_of = request.as_of or date.today()
    as_of_start = utc_midnight(as_of)
    next_day_start = utc_midnight(as_of + timedelta(days=1))

    query_vector = embed_texts([request.question])[0]
    distance = Chunk.embedding.cosine_distance(query_vector)

    statement = (
        select(
            Chunk.content,
            Chunk.chunk_index,
            Document.document_key,
            Document.title,
            DocumentVersion.version_label,
            DocumentVersion.effective_from,
            DocumentVersion.effective_to,
            distance.label("distance"),
        )
        .join(
            DocumentVersion,
            Chunk.version_id == DocumentVersion.id,
        )
        .join(
            Document,
            DocumentVersion.document_id == Document.id,
        )
        .where(
            DocumentVersion.status == "published",
            DocumentVersion.effective_from < next_day_start,
            (
                (DocumentVersion.effective_to.is_(None))
                | (DocumentVersion.effective_to > as_of_start)
            ),
            Chunk.embedding.is_not(None),
        )
    )

    if request.document_key:
        statement = statement.where(
            Document.document_key == request.document_key
        )

    rows = db.execute(
        statement.order_by(distance).limit(request.top_k)
    ).all()

    return {
        "question": request.question,
        "as_of": as_of.isoformat(),
        "results": [
            {
                "content": row.content,
                "document_key": row.document_key,
                "title": row.title,
                "version": row.version_label,
                "effective_from": row.effective_from.isoformat(),
                "effective_to": (
                    row.effective_to.isoformat()
                    if row.effective_to
                    else None
                ),
                "chunk_index": row.chunk_index,
                "similarity": round(1 - row.distance, 4),
            }
            for row in rows
        ],
    }


def test_extract_annual_leave():
    facts = extract_policy_facts(
        "Employees receive 18 days of annual leave per year."
    )

    assert len(facts) == 1
    assert facts[0]["value"] == 18
    assert facts[0]["unit"] == "days"
    assert "annual leave" in facts[0]["concept"]


def test_extract_multiple_quantities():
    facts = extract_policy_facts(
        "Employees receive 24 days of annual leave. "
        "Unused annual leave can be carried forward up to 8 days."
    )

    assert len(facts) == 2
    assert {fact["value"] for fact in facts} == {8, 24}


def test_no_numeric_policy_facts():
    facts = extract_policy_facts(
        "Employees should request leave in advance."
    )

    assert facts == []


NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "ninety": 90,
    "hundred": 100,
}

UNIT_TO_BASE = {
    "minute": ("time_minutes", 1),
    "minutes": ("time_minutes", 1),
    "hour": ("time_minutes", 60),
    "hours": ("time_minutes", 60),
    "day": ("time_days", 1),
    "days": ("time_days", 1),
    "week": ("time_days", 7),
    "weeks": ("time_days", 7),
    "month": ("time_months", 1),
    "months": ("time_months", 1),
    "year": ("time_months", 12),
    "years": ("time_months", 12),
}

def parse_number(value: str) -> float:
    value = value.strip().lower()

    if value in NUMBER_WORDS:
        return float(NUMBER_WORDS[value])

    return float(value.replace(",", ""))


def normalize_concept(concept: str) -> str:
    concept = concept.lower().strip()
    concept = re.sub(r"^(the|a|an)\s+", "", concept)
    concept = re.sub(r"\s+", " ", concept)
    concept = re.sub(r"\bemployees?\b", "", concept)
    concept = re.sub(r"\b(are|is|can|may|receive|receives|take|takes)\b", "", concept)
    concept = re.sub(r"\b(for|of|the|their)\b", "", concept)
    concept = re.sub(r"\s+", " ", concept)
    return concept.strip(" ,:-.")

def comparable_value(value, unit):
    unit = unit.lower().strip()

    if unit not in UNIT_TO_BASE:
        return value, unit

    base_unit, multiplier = UNIT_TO_BASE[unit]

    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return value, unit

    normalized = value * multiplier

    if isinstance(normalized, float) and normalized.is_integer():
        normalized = int(normalized)

    return normalized, base_unit
def extract_policy_facts(text: str) -> list[dict]:
    facts = []

    def get_sentence(position: int) -> str:
        start_candidates = [
            text.rfind(".", 0, position),
            text.rfind("!", 0, position),
            text.rfind("?", 0, position),
            text.rfind("\n", 0, position),
        ]
        start = max(start_candidates) + 1

        end_candidates = [
            pos
            for pos in (
                text.find(".", position),
                text.find("!", position),
                text.find("?", position),
                text.find("\n", position),
            )
            if pos != -1
        ]
        end = min(end_candidates) + 1 if end_candidates else len(text)

        return text[start:end].strip()

    def add_fact(concept, value, unit, source_text):
        concept = normalize_concept(concept)
        if not concept:
            return

        if isinstance(value, float) and value.is_integer():
            value = int(value)

        facts.append({
            "concept": concept,
            "value": value,
            "unit": unit.lower().strip(),
            "source_text": source_text.strip(),
        })

    number_pattern = r"(?:\d[\d,]*(?:\.\d+)?|[a-z]+)"
    time_units = r"(?:days?|weeks?|months?|years?|hours?|minutes?)"

    # Generic quantities expressed as "5 weeks of parental leave".
    generic_pattern = re.compile(
        rf"\b({number_pattern})\s+({time_units})"
        rf"\s+(?:of|for)\s+([^.!?;\n]+)",
        re.IGNORECASE,
    )

    for match in generic_pattern.finditer(text):
        try:
            value = parse_number(match.group(1))
        except (ValueError, TypeError):
            continue

        add_fact(
            match.group(3),
            value,
            match.group(2),
            get_sentence(match.start()),
        )

    # Generic numeric limits such as "within 10 days" or "up to 8 days".
    limit_pattern = re.compile(
        rf"\b(up\s+to|at\s+least|no\s+more\s+than|within|"
        rf"maximum(?:\s+of)?|minimum(?:\s+of)?)\s+"
        rf"({number_pattern})\s+({time_units})\b",
        re.IGNORECASE,
    )

    for match in limit_pattern.finditer(text):
        try:
            value = parse_number(match.group(2))
        except (ValueError, TypeError):
            continue

        sentence = get_sentence(match.start())
        quantity_start = match.start()
        sentence_start = max(
            text.rfind(".", 0, quantity_start),
            text.rfind("!", 0, quantity_start),
            text.rfind("?", 0, quantity_start),
            text.rfind("\n", 0, quantity_start),
        ) + 1

        concept_text = text[sentence_start:match.start()].strip(" ,:-")
        concept_text = re.sub(
            r"\b(up\s+to|at\s+least|no\s+more\s+than|within|"
            r"maximum(?:\s+of)?|minimum(?:\s+of)?)\s*$",
            "",
            concept_text,
            flags=re.IGNORECASE,
        ).strip(" ,:-")

        add_fact(
            concept_text or "quantity limit",
            value,
            match.group(3),
            sentence,
        )

    # Targeted rules supplement generic extraction for common concepts.
    targeted_patterns = [
        (
            "annual leave",
            rf"\b({number_pattern})\s+days?\s+of\s+annual\s+leave\b",
            "days",
        ),
        (
            "advance leave notice",
            rf"\b({number_pattern})\s+days?\s+(?:of\s+)?"
            rf"(?:advance\s+)?notice\s+(?:for|before)\s+"
            rf"(?:taking\s+)?leave\b",
            "days",
        ),
        (
            "leave carry-forward",
            rf"\b(?:carry\s+forward|carried\s+forward|carryover|"
            rf"carry-over)\b[^.!?;\n]{{0,100}}?"
            rf"\b({number_pattern})\s+days?\b",
            "days",
        ),
        (
            "payslip error reporting deadline",
            rf"\b({number_pattern})\s+business\s+days?\s+"
            rf"(?:to|for)\s+(?:report|reporting)\s+"
            rf"(?:a\s+)?(?:payslip|pay\s+slip)\s+errors?\b",
            "business_days",
        ),
        (
            "expense claim deadline",
            rf"\b({number_pattern})\s+calendar\s+days?\s+"
            rf"(?:to|for)\s+(?:submit|filing|file)\s+"
            rf"(?:an?\s+)?expense\s+claims?\b",
            "calendar_days",
        ),
        (
            "remote work urgent response time",
            rf"\b(?:respond|response)\b[^.!?;\n]{{0,100}}?"
            rf"\bwithin\s+({number_pattern})\s+"
            rf"(minutes?|hours?)\b",
            None,
        ),
        (
            "purchase approval threshold",
            r"\b(?:purchases?|expenses?)\b[^.!?;\n]{0,100}?"
            r"\b(?:above|over|exceeding|greater\s+than)\s+"
            r"(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)\b",
            "currency",
        ),
        (
            "handbook acknowledgement deadline",
            rf"\b({number_pattern})\s+business\s+days?\s+"
            rf"(?:to|for)\s+(?:acknowledge|acknowledgement|"
            rf"acknowledgment)\b",
            "business_days",
        ),
    ]

    preferred_concepts = {
        "annual leave",
        "advance leave notice",
        "leave carry-forward",
        "leave carry-forward expiry",
        "payslip error reporting deadline",
        "expense claim deadline",
        "remote work urgent response time",
        "purchase approval threshold",
        "handbook acknowledgement deadline",
    }

    for concept, pattern, fixed_unit in targeted_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                value = parse_number(match.group(1))
            except (ValueError, TypeError):
                continue

            unit = fixed_unit
            if unit is None:
                unit = match.group(2).lower()

            add_fact(
                concept,
                value,
                unit,
                get_sentence(match.start()),
            )

    # Recurring frequencies normalized to events per year.
    frequency_patterns = [
        (
            r"\b(once|twice|three times|four times)\s+per\s+year\b",
            {"once": 1, "twice": 2, "three times": 3, "four times": 4},
        ),
        (
            r"\b(once|twice|three times|four times)\s+per\s+quarter\b",
            {"once": 4, "twice": 8, "three times": 12, "four times": 16},
        ),
        (
            r"\b(once|twice|three times|four times)\s+per\s+month\b",
            {"once": 12, "twice": 24, "three times": 36, "four times": 48},
        ),
    ]

    for pattern, multipliers in frequency_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            frequency = match.group(1).lower()
            value = multipliers[frequency]
            sentence = get_sentence(match.start())

            concept_text = re.sub(
                pattern,
                "",
                sentence,
                flags=re.IGNORECASE,
            )
            concept_text = re.sub(
                r"\b(is|are|held|conducted|performed|completed|done)\b",
                " ",
                concept_text,
                flags=re.IGNORECASE,
            )
            concept_text = re.sub(r"\s+", " ", concept_text).strip(" ,:-.")

            add_fact(
                concept_text or "recurrence",
                value,
                "events_per_year",
                sentence,
            )

    # Extract carried-forward leave expiry dates before generic dates.
    expiry_pattern = re.compile(
        r"\b(?:carried[- ]forward|carry[- ]forward)\s+days?\b"
        r"[^.!?;\n]{0,100}?\b(?:used|taken|utilized|utilised|expire)"
        r"[^.!?;\n]{0,50}?\bby\s+"
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{1,2})\b",
        re.IGNORECASE,
    )

    expiry_date_spans = set()

    for match in expiry_pattern.finditer(text):
        expiry_date_spans.add(match.span(1))

        add_fact(
            "leave carry-forward expiry",
            f"{match.group(1).title()} {int(match.group(2))}",
            "date",
            get_sentence(match.start()),
        )

    # Extract other explicit calendar dates.
    date_pattern = re.compile(
        r"\b(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{1,2})\b",
        re.IGNORECASE,
    )

    for match in date_pattern.finditer(text):
        if match.span(1) in expiry_date_spans:
            continue

        sentence = get_sentence(match.start())

        add_fact(
            sentence[:match.start()].strip(" ,:-") or "specified date",
            f"{match.group(1).title()} {int(match.group(2))}",
            "date",
            sentence,
        )

    # Deduplicate facts from the same evidence and equivalent quantities.
    # Prefer specific concepts over generic concepts for the same evidence.
    unique_facts = {}

    for fact in facts:
        comparison_value, canonical_unit = comparable_value(
            fact["value"],
            fact["unit"],
        )

        evidence = re.sub(
            r"\s+",
            " ",
            fact["source_text"].lower(),
        ).strip()

        key = (
            evidence,
            comparison_value,
            canonical_unit,
        )

        current = unique_facts.get(key)

        is_preferred = fact["concept"] in preferred_concepts
        current_is_preferred = (
            current is not None
            and current["concept"] in preferred_concepts
        )

        if current is None or (is_preferred and not current_is_preferred):
            unique_facts[key] = fact

    return list(unique_facts.values())

def classify_policy_change(concept: str, old_value: float, new_value: float) -> str:
    concept = concept.lower()

    more_is_better = (
        "annual leave",
        "leave carry-forward",
        "expense claim deadline",
        "payslip error reporting deadline",
    )

    less_is_better = (
        "advance notice",
        "advance request",
        "advance leave notice",
    )

    if any(term in concept for term in more_is_better):
        return (
            "more_employee_favorable"
            if new_value > old_value
            else "less_employee_favorable"
        )

    if any(term in concept for term in less_is_better):
        return (
            "more_employee_favorable"
            if new_value < old_value
            else "less_employee_favorable"
        )

    return "context_dependent"


def reconstruct_text(chunks: list[Chunk], overlap: int = 30) -> str:
    if not chunks:
        return ""

    words = chunks[0].content.split()

    for chunk in chunks[1:]:
        next_words = chunk.content.split()
        words.extend(next_words[overlap:])

    return " ".join(words)


@router.get("/{document_key}/compare")
@router.get("/{document_key}/compare")
def compare_versions(
    document_key: str,
    from_version: str,
    to_version: str,
    db: Session = Depends(get_db),
):
    if from_version == to_version:
        raise HTTPException(
            status_code=400,
            detail="Choose two different versions to compare.",
        )

    document = db.scalar(
        select(Document).where(
            Document.document_key == document_key
        )
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    versions = db.scalars(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document.id,
            DocumentVersion.version_label.in_(
                [from_version, to_version]
            ),
        )
    ).all()

    version_map = {
        version.version_label: version
        for version in versions
    }

    old_version = version_map.get(from_version)
    new_version = version_map.get(to_version)

    if old_version is None or new_version is None:
        raise HTTPException(
            status_code=404,
            detail="One or both versions were not found.",
        )

    if (
        old_version.status != "published"
        or new_version.status != "published"
    ):
        raise HTTPException(
            status_code=409,
            detail="Both versions must be published before comparison.",
        )

    old_chunks = db.scalars(
        select(Chunk)
        .where(Chunk.version_id == old_version.id)
        .order_by(Chunk.chunk_index)
    ).all()

    new_chunks = db.scalars(
        select(Chunk)
        .where(Chunk.version_id == new_version.id)
        .order_by(Chunk.chunk_index)
    ).all()

    old_text = reconstruct_text(old_chunks)
    new_text = reconstruct_text(new_chunks)

    old_facts = extract_policy_facts(old_text)
    new_facts = extract_policy_facts(new_text)

    def build_fact_map(facts):
        result = {}

        for fact in facts:
            comparison_value, canonical_unit = comparable_value(
                fact["value"],
                fact["unit"],
            )

            key = (
                normalize_concept(fact["concept"]),
                canonical_unit,
            )

            # Avoid silently overwriting duplicate concepts with
            # different evidence or values.
            if key not in result:
                result[key] = {
                    **fact,
                    "comparison_value": comparison_value,
                    "comparison_unit": canonical_unit,
                }

        return result

    old_fact_map = build_fact_map(old_facts)
    new_fact_map = build_fact_map(new_facts)

    fact_changes = []

    # Compare facts present in both versions.
    for key in old_fact_map.keys() & new_fact_map.keys():
        old_fact = old_fact_map[key]
        new_fact = new_fact_map[key]

        old_value = old_fact["value"]
        new_value = new_fact["value"]

        old_comparison = old_fact["comparison_value"]
        new_comparison = new_fact["comparison_value"]

        # Different written units can represent the same quantity,
        # such as five weeks and thirty-five days.
        if old_comparison == new_comparison:
            continue

        numeric_values = (
            isinstance(old_comparison, (int, float))
            and not isinstance(old_comparison, bool)
            and isinstance(new_comparison, (int, float))
            and not isinstance(new_comparison, bool)
        )

        if numeric_values:
            change_type = (
                "increased"
                if new_comparison > old_comparison
                else "decreased"
            )

            difference = round(
                new_comparison - old_comparison,
                2,
            )

            impact = classify_policy_change(
                old_fact["concept"],
                old_comparison,
                new_comparison,
            )
        else:
            change_type = "modified"
            difference = None
            impact = "context_dependent"

        fact_changes.append({
            "concept": old_fact["concept"],
            "change_type": change_type,
            "old_value": old_value,
            "new_value": new_value,
            "difference": difference,
            "unit": old_fact["unit"],
            "comparison_unit": old_fact["comparison_unit"],
            "impact": impact,
            "old_evidence": old_fact["source_text"],
            "new_evidence": new_fact["source_text"],
        })

    # Facts present in the old version but not the new version.
    for key in old_fact_map.keys() - new_fact_map.keys():
        fact = old_fact_map[key]

        fact_changes.append({
            "concept": fact["concept"],
            "change_type": "removed",
            "old_value": fact["value"],
            "new_value": None,
            "difference": None,
            "unit": fact["unit"],
            "comparison_unit": fact["comparison_unit"],
            "impact": "context_dependent",
            "old_evidence": fact["source_text"],
            "new_evidence": None,
        })

    # Facts introduced in the new version.
    for key in new_fact_map.keys() - old_fact_map.keys():
        fact = new_fact_map[key]

        fact_changes.append({
            "concept": fact["concept"],
            "change_type": "added",
            "old_value": None,
            "new_value": fact["value"],
            "difference": None,
            "unit": fact["unit"],
            "comparison_unit": fact["comparison_unit"],
            "impact": "context_dependent",
            "old_evidence": None,
            "new_evidence": fact["source_text"],
        })

    # Compare the original text at sentence level as well.
    def split_sentences(text: str) -> list[str]:
        return [
            sentence.strip()
            for sentence in re.split(
                r"(?<=[.!?])\s+|\n+",
                text,
            )
            if sentence.strip()
        ]

    old_sentences = split_sentences(old_text)
    new_sentences = split_sentences(new_text)

    matcher = SequenceMatcher(
        None,
        old_sentences,
        new_sentences,
        autojunk=False,
    )

    changes = []

    for operation, i1, i2, j1, j2 in matcher.get_opcodes():
        if operation == "equal":
            continue

        removed = old_sentences[i1:i2]
        added = new_sentences[j1:j2]

        changes.append({
            "change_type": {
                "replace": "modified",
                "delete": "removed",
                "insert": "added",
            }[operation],
            "old_text": " ".join(removed),
            "new_text": " ".join(added),
        })

    return {
        "document_key": document_key,
        "title": document.title,
        "from_version": {
            "version": old_version.version_label,
            "effective_from": old_version.effective_from.isoformat(),
        },
        "to_version": {
            "version": new_version.version_label,
            "effective_from": new_version.effective_from.isoformat(),
        },
        "total_changes": len(changes),
        "changes": changes,
        "fact_changes": fact_changes,
    }

@router.post("/answer")
def answer_question(
    request: AnswerRequest,
    db: Session = Depends(get_db),
):
    as_of = request.as_of or date.today()
    as_of_start = utc_midnight(as_of)
    next_day_start = utc_midnight(as_of + timedelta(days=1))

    query_vector = embed_texts([request.question])[0]
    distance = Chunk.embedding.cosine_distance(query_vector)

    statement = (
        select(
            Chunk.content,
            Chunk.chunk_index,
            Document.document_key,
            Document.title,
            DocumentVersion.version_label,
            DocumentVersion.effective_from,
            DocumentVersion.effective_to,
            distance.label("distance"),
        )
        .join(
            DocumentVersion,
            Chunk.version_id == DocumentVersion.id,
        )
        .join(
            Document,
            DocumentVersion.document_id == Document.id,
        )
        .where(
            DocumentVersion.status == "published",
            DocumentVersion.effective_from < next_day_start,
            (
                DocumentVersion.effective_to.is_(None)
                | (DocumentVersion.effective_to > as_of_start)
            ),
            Chunk.embedding.is_not(None),
        )
    )

    if request.document_key:
        statement = statement.where(
            Document.document_key == request.document_key
        )

    rows = db.execute(
        statement.order_by(distance).limit(request.top_k)
    ).all()

    
    if not rows:
        return {
            "question": request.question,
            "as_of": as_of.isoformat(),
            "answer": None,
            "message": "No relevant published evidence was found.",
            "citations": [],
        }

    passages = [
        {
            "source_id": f"S{i + 1}",
            "content": row.content,
        }
        for i, row in enumerate(rows)
    ]

    answer = generate_grounded_answer(
        question=request.question,
        passages=passages,
    )
    citation_validation = validate_source_ids(answer, passages)
    citations = [
        {
            "source_id": f"S{i + 1}",
            "document_key": row.document_key,
            "title": row.title,
            "version": row.version_label,
            "effective_from": row.effective_from.isoformat(),
            "effective_to": (
                row.effective_to.isoformat()
                if row.effective_to
                else None
            ),
            "chunk_index": row.chunk_index,
            "similarity": round(1 - row.distance, 4),
            "quoted_text": row.content,
        }
        for i, row in enumerate(rows)
    ]

    return {
        "question": request.question,
        "as_of": as_of.isoformat(),
        "answer": answer,
        "answer_type": (
            "extractive"
            if os.getenv("LLM_PROVIDER", "ollama").lower() == "extractive"
            else "llm_grounded"
        ),
        "citations": citations,
        "citation_validation": citation_validation,
    }
