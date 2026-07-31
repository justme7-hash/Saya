"""سرور سلامت‌سنج (Health Check) HTTP.

این سرور کوچک روی یک پورت جداگانه اجرا می‌شود و به Railway
اجازه می‌دهد سلامت ربات را بررسی کند. در پلن رایگان Railway،
این بررسی الزامی است.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from aiohttp import web

from anonchat.core.logging import get_logger

if TYPE_CHECKING:
    from anonchat.core.container import Container

_log = get_logger("health")


class HealthServer:
    """سرور سلامت‌سنج سبک."""

    def __init__(self, container: Container, port: int) -> None:
        self._container = container
        self._port = port
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        """شروع سرور."""
        app = web.Application()
        app.router.add_get("/health", self._health_handler)
        app.router.add_get("/", self._root_handler)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()
        _log.info("health.server_started", port=self._port)

    async def stop(self) -> None:
        """توقف سرور."""
        if self._runner is not None:
            await self._runner.cleanup()
            _log.info("health.server_stopped")

    async def _health_handler(self, request: web.Request) -> web.Response:
        """اندپوینت سلامت‌سنج."""
        try:
            health = await self._container.admin_service.get_system_health()
            status_code = 200 if health.status == "healthy" else 503
            return web.json_response(
                text=health.model_dump_json(),
                status=status_code,
                content_type="application/json",
            )
        except Exception as exc:
            _log.error("health.check_failed", error=str(exc))
            return web.json_response(
                {"status": "down", "error": str(exc)},
                status=503,
            )

    async def _root_handler(self, request: web.Request) -> web.Response:
        """صفحه‌ی اصلی — اطلاعات ساده."""
        return web.Response(
            text=json.dumps(
                {
                    "name": "Saya Anonymous Chat Bot",
                    "status": "running",
                    "version": "1.0.0",
                },
                ensure_ascii=False,
            ),
            content_type="application/json",
        )
