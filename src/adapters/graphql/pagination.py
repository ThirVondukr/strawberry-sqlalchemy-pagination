import base64
import dataclasses
from collections.abc import Sequence
from typing import Any, Generic, Literal, Protocol, TypeVar

import strawberry
from sqlalchemy import Select, Text, cast, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from db import Base

TEdge = TypeVar("TEdge")
TModel_contra = TypeVar("TModel_contra", bound=Base, contravariant=True)
TNode = TypeVar("TNode")
TType_co = TypeVar("TType_co", covariant=True)


@strawberry.type(name="PageInfo")
class PageInfo:
    has_next_page: bool = False
    has_previous_page: bool = False
    start_cursor: str = ""
    end_cursor: str = ""


@strawberry.input(name="PaginationInput")
class PaginationInput:
    first: int | None = None
    after: str | None = None

    last: int | None = None
    before: str | None = None


@strawberry.type(name="Edge")
class Edge(Generic[TNode]):
    node: TNode
    cursor: str


@strawberry.type(name="Connection")
class Connection(Generic[TEdge]):
    edges: list[TEdge]
    page_info: PageInfo


@dataclasses.dataclass
class _Pagination:
    cursor: str | None
    take: int
    order: Literal["asc", "desc"]


class GQLProtocol(Protocol[TModel_contra, TType_co]):
    @classmethod
    def from_orm(cls, model: TModel_contra) -> TType_co:
        ...


class CursorPagination(Generic[TModel_contra, TType_co]):
    def __init__(
        self,
        model: type[TModel_contra],
        type_: type[GQLProtocol[TModel_contra, TType_co]],
        fields: Sequence[InstrumentedAttribute[Any]],
        separator: str = ":",
    ) -> None:
        self._model = model
        self._type = type_
        self._fields = fields
        self._types = [field.type for field in fields]
        self._separator = separator

    def decode_cursor(self, cursor: str) -> Sequence[Any]:
        parts = [
            base64.b64decode(part).decode() for part in cursor.split(self._separator)
        ]
        return [
            cast(part, Text).cast(type_)
            for type_, part in zip(self._types, parts, strict=True)
        ]

    def encode_cursor(self, model: TModel_contra) -> str:
        values = [
            base64.b64encode(str(getattr(model, field.key)).encode()).decode()
            for field in self._fields
        ]
        return self._separator.join(values)

    async def paginate(
        self,
        session: AsyncSession,
        pagination: PaginationInput,
        stmt: Select[tuple[TModel_contra]],
    ) -> Connection[Edge[TType_co]]:
        if pagination.first and pagination.last:
            msg = (
                "Providing both 'first' and 'last' arguments "
                "is generally undesirable according to spec"
            )
            raise ValueError(msg)

        if pagination.after:
            cursor = self.decode_cursor(pagination.after)
            stmt = stmt.where(tuple_(*self._fields) > tuple_(*cursor))
        if pagination.before:
            cursor = self.decode_cursor(pagination.before)
            stmt = stmt.where(tuple_(*self._fields) < tuple_(*cursor))

        limit = pagination.first or pagination.last
        if limit is None:
            raise ValueError

        if limit <= 0:
            raise ValueError

        stmt = stmt.limit(limit + 1)
        if pagination.first:
            stmt = stmt.order_by(*self._fields)
        if pagination.last:
            stmt = stmt.order_by(*(c.desc() for c in self._fields))

        result = (await session.scalars(stmt)).all()
        if pagination.last:
            result = result[::-1]

        return Connection(
            edges=[
                Edge(node=self._type.from_orm(model), cursor=self.encode_cursor(model))
                for model in result[:limit]
            ],
            page_info=PageInfo(
                has_next_page=len(result) > limit,
                has_previous_page=False,
                start_cursor=self.encode_cursor(result[0]) if result else "",
                end_cursor=self.encode_cursor(result[-1]) if result else "",
            ),
        )
