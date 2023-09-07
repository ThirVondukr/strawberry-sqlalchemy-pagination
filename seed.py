import asyncio

from faker import Faker
from sqlalchemy import delete

from db import async_session_factory
from db.models import Book


async def main() -> None:
    fake = Faker()

    async with async_session_factory.begin() as session:
        await session.execute(delete(Book))
        for _ in range(1_000):
            session.add(Book(title=fake.sentence()))


if __name__ == "__main__":
    asyncio.run(main())
