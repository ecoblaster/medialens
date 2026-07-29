from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.library import Library
from app.schemas.library import LibraryCreate, LibraryRead, LibraryUpdate

router = APIRouter(prefix="/libraries", tags=["libraries"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def get_library_or_404(library_id: str, db: Session) -> Library:
    library = db.get(Library, library_id)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "LIBRARY_NOT_FOUND",
                "message": "The requested library does not exist.",
                "details": {"library_id": library_id},
            },
        )
    return library


@router.get("", response_model=list[LibraryRead])
def list_libraries(db: DatabaseSession) -> list[Library]:
    return list(db.scalars(select(Library).order_by(Library.name)).all())


@router.post("", response_model=LibraryRead, status_code=status.HTTP_201_CREATED)
def create_library(payload: LibraryCreate, db: DatabaseSession) -> Library:
    library = Library(**payload.model_dump(mode="json"))
    db.add(library)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "LIBRARY_ALREADY_EXISTS",
                "message": "A library with this source type and root path already exists.",
                "details": {
                    "source_type": payload.source_type,
                    "root_path": payload.root_path,
                },
            },
        ) from exc
    db.refresh(library)
    return library


@router.get("/{library_id}", response_model=LibraryRead)
def read_library(library_id: str, db: DatabaseSession) -> Library:
    return get_library_or_404(library_id, db)


@router.patch("/{library_id}", response_model=LibraryRead)
def update_library(
    library_id: str, payload: LibraryUpdate, db: DatabaseSession
) -> Library:
    library = get_library_or_404(library_id, db)
    for field, value in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(library, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "LIBRARY_ALREADY_EXISTS",
                "message": "A library with this source type and root path already exists.",
                "details": {},
            },
        ) from exc
    db.refresh(library)
    return library


@router.delete("/{library_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_library(library_id: str, db: DatabaseSession) -> Response:
    library = get_library_or_404(library_id, db)
    db.delete(library)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
