
from sqlalchemy import select

from app.database import SessionLocal
from app.embeddings import embed_texts
from app.models import Chunk


BATCH_SIZE = 32


def main():
    db = SessionLocal()

    try:
        chunks = db.scalars(
            select(Chunk)
            .where(Chunk.embedding.is_(None))
            .order_by(Chunk.id)
        ).all()

        total = len(chunks)
        print(f"Chunks requiring embeddings: {total}")

        for start in range(0, total, BATCH_SIZE):
            batch = chunks[start:start + BATCH_SIZE]
            vectors = embed_texts([chunk.content for chunk in batch])

            for chunk, vector in zip(batch, vectors):
                chunk.embedding = vector

            db.commit()
            print(
                f"Embedded {min(start + len(batch), total)}/{total} chunks"
            )

        print("Embedding backfill completed successfully.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
