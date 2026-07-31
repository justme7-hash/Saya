"""سرویس پیام — رله‌ی پیام‌ها بین کاربران در گفتگو.

این سرویس مسئول:
- تشخیص نوع پیام و ارسال به شریک
- ثبت متادیتای پیام (نه محتوا — حفظ حریم خصوصی)
- مدیریت آلبوم (گروه پیام‌های رسانه‌ای)
- Reply / Forward
- تایپ‌کردن (chat action)
- پاداش XP برای ارسال/دریافت پیام
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from aiogram import Bot
from aiogram.enums import ChatAction, ContentType
from aiogram.types import Message

from anonchat.core.logging import get_logger
from anonchat.core.security import sanitize_text
from anonchat.models.message import Message as MessageModel

if TYPE_CHECKING:
    from anonchat.core.container import Container


# نگاشت نوع محتوا به متد ارسال مجدد
_CONTENT_METHOD_MAP: dict[str, str] = {
    ContentType.TEXT: "send_message",
    ContentType.PHOTO: "send_photo",
    ContentType.VIDEO: "send_video",
    ContentType.DOCUMENT: "send_document",
    ContentType.AUDIO: "send_audio",
    ContentType.VOICE: "send_voice",
    ContentType.VIDEO_NOTE: "send_video_note",
    ContentType.STICKER: "send_sticker",
    ContentType.ANIMATION: "send_animation",
    ContentType.LOCATION: "send_location",
    ContentType.CONTACT: "send_contact",
    ContentType.POLL: "send_poll",
}

# نوع پیام قابل ذخیره در دیتابیس
_TYPE_LABEL_MAP: dict[str, str] = {
    ContentType.TEXT: "text",
    ContentType.PHOTO: "photo",
    ContentType.VIDEO: "video",
    ContentType.DOCUMENT: "document",
    ContentType.AUDIO: "audio",
    ContentType.VOICE: "voice",
    ContentType.VIDEO_NOTE: "video_note",
    ContentType.STICKER: "sticker",
    ContentType.ANIMATION: "gif",
    ContentType.LOCATION: "location",
    ContentType.CONTACT: "contact",
    ContentType.POLL: "poll",
}


class MessageService:
    """سرویس رله‌ی پیام بین کاربران."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._log = get_logger("service.message")

    async def relay(
        self,
        bot: Bot,
        message: Message,
        *,
        partner_telegram_id: int,
        chat_session_id: int,
        sender_telegram_id: int,
    ) -> bool:
        """رله‌ی یک پیام به شریک گفتگو.

        Returns:
            True اگر رله موفق بود.
        """
        content_type = message.content_type

        if content_type not in _CONTENT_METHOD_MAP:
            self._log.warning(
                "message.unsupported_type",
                type=content_type,
                sender=sender_telegram_id,
            )
            return False

        # پاک‌سازی متن (اگر متنی دارد)
        caption = message.caption or message.text
        sanitized_caption = sanitize_text(caption) if caption else None

        try:
            await self._send_to_partner(
                bot, message, partner_telegram_id, sanitized_caption
            )
        except Exception as exc:
            self._log.error(
                "message.relay_failed",
                sender=sender_telegram_id,
                partner=partner_telegram_id,
                error=str(exc),
            )
            return False

        # ثبت متادیتا
        await self._record_message(
            chat_session_id=chat_session_id,
            sender_telegram_id=sender_telegram_id,
            message=message,
            content_type=content_type,
        )

        # پاداش XP
        await self._container.user_service.add_xp(sender_telegram_id, 1)

        return True

    async def _send_to_partner(
        self,
        bot: Bot,
        message: Message,
        partner_id: int,
        caption: str | None,
    ) -> None:
        """ارسال پیام به شریک با روش مناسب."""
        ct = message.content_type

        if ct == ContentType.TEXT:
            await bot.send_message(partner_id, text=caption or "")
        elif ct == ContentType.PHOTO:
            await bot.send_photo(
                partner_id,
                photo=message.photo[-1].file_id,
                caption=caption,
            )
        elif ct == ContentType.VIDEO:
            await bot.send_video(
                partner_id,
                video=message.video.file_id,
                caption=caption,
            )
        elif ct == ContentType.DOCUMENT:
            await bot.send_document(
                partner_id,
                document=message.document.file_id,
                caption=caption,
            )
        elif ct == ContentType.AUDIO:
            await bot.send_audio(
                partner_id,
                audio=message.audio.file_id,
                caption=caption,
            )
        elif ct == ContentType.VOICE:
            await bot.send_voice(partner_id, voice=message.voice.file_id)
        elif ct == ContentType.VIDEO_NOTE:
            await bot.send_video_note(
                partner_id, video_note=message.video_note.file_id
            )
        elif ct == ContentType.STICKER:
            await bot.send_sticker(partner_id, sticker=message.sticker.file_id)
        elif ct == ContentType.ANIMATION:
            await bot.send_animation(
                partner_id,
                animation=message.animation.file_id,
                caption=caption,
            )
        elif ct == ContentType.LOCATION:
            loc = message.location
            await bot.send_location(
                partner_id,
                latitude=loc.latitude,
                longitude=loc.longitude,
            )
        elif ct == ContentType.CONTACT:
            contact = message.contact
            await bot.send_contact(
                partner_id,
                phone_number=contact.phone_number,
                first_name=contact.first_name,
                last_name=contact.last_name,
            )
        elif ct == ContentType.POLL:
            poll = message.poll
            await bot.send_poll(
                partner_id,
                question=poll.question,
                options=[opt.text for opt in poll.options],
                is_anonymous=poll.is_anonymous,
            )

    async def _record_message(
        self,
        *,
        chat_session_id: int,
        sender_telegram_id: int,
        message: Message,
        content_type: str,
    ) -> None:
        """ثبت متادیتای پیام در دیتابیس (بدون محتوای قابل خواندن)."""
        text_content = message.text or message.caption or ""
        text_length = len(text_content) if text_content else None
        # هش محتوا برای تشخیص اسپم تکراری (نه محتوای قابل خواندن)
        content_hash = None
        if text_content:
            content_hash = hashlib.sha256(
                text_content.encode()
            ).hexdigest()[:32]

        file_id = None
        file_unique_id = None
        for attr in ("photo", "video", "document", "audio", "voice", "animation"):
            obj = getattr(message, attr, None)
            if obj is not None:
                if isinstance(obj, list) and obj:
                    file_id = obj[-1].file_id
                    file_unique_id = obj[-1].file_unique_id
                elif hasattr(obj, "file_id"):
                    file_id = obj.file_id
                    file_unique_id = getattr(obj, "file_unique_id", None)
                break
        if message.video_note is not None:
            file_id = message.video_note.file_id
            file_unique_id = message.video_note.file_unique_id
        if message.sticker is not None:
            file_id = message.sticker.file_id

        async with self._container.session() as session:
            user_repo = self._container.user_repo_with(session)
            chat_repo = self._container.chat_repo_with(session)

            sender = await user_repo.get_by_telegram_id(sender_telegram_id)
            if sender is None:
                return

            record = MessageModel(
                chat_session_id=chat_session_id,
                sender_id=sender.id,
                message_type=_TYPE_LABEL_MAP.get(content_type, content_type),
                text_length=text_length,
                content_hash=content_hash,
                content_preview=None,  # فقط هنگام گزارش پر می‌شود
                file_id=file_id,
                file_unique_id=file_unique_id,
                is_forwarded="true" if message.forward_date else "false",
                is_reply="true" if message.reply_to_message else "false",
            )
            session.add(record)
            await chat_repo.increment_message_count(chat_session_id)
            await session.commit()

    async def send_chat_action(
        self, bot: Bot, partner_telegram_id: int, action: str = "typing"
    ) -> None:
        """ارسال وضعیت «در حال تایپ» و类似 به شریک."""
        try:
            chat_action = ChatAction(action)
            await bot.send_chat_action(partner_telegram_id, chat_action)
        except (ValueError, TypeError) as exc:
            self._log.debug("chat_action_failed", error=str(exc))
        except Exception as exc:
            # خطاهای شبکه (مثل Forbidden) نباید ربات را متوقف کنند
            self._log.debug("chat_action_network_error", error=str(exc))

    async def relay_album(
        self,
        bot: Bot,
        messages: list[Message],
        *,
        partner_telegram_id: int,
        chat_session_id: int,
        sender_telegram_id: int,
    ) -> int:
        """رله‌ی آلبوم (گروه پیام‌های رسانه‌ای) به شریک.

        Telegram MediaGroup را به‌صورت چند پیام با media_group_id می‌فرستد.
        ما آن‌ها را به‌صورت یک گروه ارسال می‌کنیم.

        Returns:
            تعداد پیام‌های موفق.
        """
        if not messages:
            return 0

        # ارسال اولین پیام به‌صورت عادی
        count = 0
        for msg in messages:
            ok = await self.relay(
                bot,
                msg,
                partner_telegram_id=partner_telegram_id,
                chat_session_id=chat_session_id,
                sender_telegram_id=sender_telegram_id,
            )
            if ok:
                count += 1
        return count
