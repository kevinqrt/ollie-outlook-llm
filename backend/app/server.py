import uvicorn

from app.core.config import settings


def main() -> None:
    uvicorn.run(
        "app.app:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        ssl_certfile=settings.ssl_certfile or None,
        ssl_keyfile=settings.ssl_keyfile or None,
    )


if __name__ == "__main__":
    main()
