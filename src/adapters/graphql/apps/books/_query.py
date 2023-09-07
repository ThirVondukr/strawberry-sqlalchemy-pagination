from typing import Annotated

import strawberry
from aioinject import Inject
from aioinject.ext.strawberry import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.graphql.pagination import (
    Connection,
    CursorPagination,
    Edge,
    PaginationInput,
)
from core.books.queries import BookGetQuery
from db.models import Book

from .types import BookGQL


@strawberry.type
class BookQuery:
    @strawberry.field
    @inject
    async def book(
        self,
        id_: Annotated[strawberry.ID, strawberry.argument(name="id")],
        query: Annotated[BookGetQuery, Inject],
    ) -> BookGQL | None:
        try:
            int_id = int(id_)
        except ValueError:
            return None

        book = await query.execute(book_id=int_id)
        return BookGQL.from_orm_optional(book)

    @strawberry.field
    @inject
    async def books(
        self,
        pagination: PaginationInput,
        session: Annotated[AsyncSession, Inject],
    ) -> Connection[Edge[BookGQL]]:
        paginator = CursorPagination(
            model=Book,
            type_=BookGQL,
            fields=[Book.title, Book.id],
        )
        return await paginator.paginate(
            session=session,
            pagination=pagination,
            stmt=select(Book),
        )
