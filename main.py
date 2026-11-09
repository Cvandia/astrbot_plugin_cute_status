"""AstrBot entry point."""

import asyncio
import time

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Image
from astrbot.api.star import Context, Star, register

from .config import Settings
from .renderer import render
from .status import collect, text_status


@register(
    "astrbot-plugin-cute-status",
    "Cvandia",
    "可爱的服务器状态卡片",
    "1.0.4",
    "https://github.com/Cvandia/astrbot-plugin-cute-status",
)
class CuteStatusPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.settings = Settings.parse(config)
        self._lock = asyncio.Lock()
        self._last_success: float | None = None
        self._worker: asyncio.Task | None = None

    @filter.command("status", alias={"状态", "运行状态"})
    async def status(self, event: AstrMessageEvent):
        """查看 CPU、内存、交换区、磁盘和运行时长。"""
        cfg = self.settings
        if cfg.only_admin and not event.is_admin():
            event.stop_event()
            yield event.plain_result("只有 AstrBot 管理员可以查看运行状态。")
            return
        if cfg.to_me and not event.is_private_chat():
            mentioned = any(
                isinstance(c, At) and str(c.qq) == str(event.get_self_id())
                for c in event.get_messages()
            )
            if not mentioned:
                event.stop_event()
                yield event.plain_result("请 @机器人 后使用运行状态指令。")
                return
        event.stop_event()
        if self._lock.locked() or (self._worker is not None and not self._worker.done()):
            yield event.plain_result("正在绘制状态卡片，请稍后再试。")
            return
        async with self._lock:
            if self._last_success is not None:
                remaining = cfg.cooldown - (time.monotonic() - self._last_success)
                if remaining > 0:
                    yield event.plain_result(f"状态查询冷却中，请 {remaining:.0f} 秒后再试。")
                    return
            try:
                plugins = sum(
                    bool(getattr(s, "activated", True)) for s in self.context.get_all_stars()
                )
                # Shield keeps the worker tracked when a request is cancelled:
                # to_thread cancellation alone cannot stop its underlying thread.
                self._worker = asyncio.create_task(asyncio.to_thread(self._build, plugins))
                self._worker.add_done_callback(self._observe_worker)
                result = await asyncio.shield(self._worker)
            except Exception:
                logger.exception("Cute Status: 状态采集失败")
                yield event.plain_result("状态采集失败，请检查磁盘路径及 AstrBot 日志。")
                return
            self._last_success = time.monotonic()
            if isinstance(result, bytes):
                yield event.chain_result([Image.fromBytes(result)])
            else:
                yield event.plain_result(result)

    def _build(self, plugins: int) -> bytes | str:
        data = collect(self.settings.disk_path, plugins)
        try:
            return render(data, self.settings.nickname, self.settings.font_path)
        except Exception:
            logger.exception("Cute Status: 绘图失败，改为文本回复")
            return text_status(data, self.settings.nickname)

    async def terminate(self):
        if self._worker is not None:
            await asyncio.gather(self._worker, return_exceptions=True)

    @staticmethod
    def _observe_worker(task):
        # Retrieve exceptions even if the event awaiting this worker was cancelled.
        if not task.cancelled():
            task.exception()
