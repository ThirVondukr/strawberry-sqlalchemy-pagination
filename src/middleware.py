from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class CommitSessionMiddleware:
    def __init__(
        self,
        app: ASGIApp,
    ) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def _inner(message: Message) -> None:
            if message["type"] != "http.response.start":
                await send(message)
                return
            if "state" in scope and (
                session := scope["state"].get("sqlalchemy_session")
            ):
                if session.in_transaction():
                    await session.commit()
            await send(message)

        await self.app(scope, receive, _inner)
