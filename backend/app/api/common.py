from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def paginated(db: Session, statement: Any, count_statement: Any, limit: int, offset: int) -> dict[str, Any]:
    items = list(db.scalars(statement.limit(limit).offset(offset)).all())
    total = int(db.scalar(count_statement) or 0)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def count_for(model: Any) -> Any:
    return select(func.count()).select_from(model)
