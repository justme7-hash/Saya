"""سرویس پیام ناشناس — ارسال و دریافت پیام از طریق لینک ناشناس.

قابلیت‌ها:
- تولید لینک اختصاصی برای هر کاربر
- دریافت پیام ناشناس از طریق لینک
- رله‌ی پیام به صاحب لینک
- پاسخ‌دهی به پیام ناشناس
- فوروارد پیام به کانال/گروه
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from aiogram import Bot
from aiogram.types import Message

from anonchat.core.exceptions import UserNotFoundError
from anonchat.core.logging import get_logger
from anonchat.models.anonymous_message import AnonymousMessage

if TYPE_CHECKING:
    from anonchat.core.container import Container


# تعداد پیام ناشناس مجاز در پنجره زمانی
ANON_RATE_LIMIT = 5
ANON_RATE_WINDOW_HOURS = 1


class AnonymousMessageService:
    """سرویس مدیریت پیام‌های ناشناس."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._log = get_logger("service.anon")

    async def get_anon_link(self, telegram_id: int) -> str:
        """دریافت لینک پیام ناشناس کاربر.

        از referral_code کاربر برای ساخت لینک استفاده می‌شود.
        لینک: https://t.me/BOT_USERNAME?start=anon_{referral_code}
        """
        async with self._container.session() as session:
            user_repo = self._container.user_repo_with(session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                raise UserNotFoundError(telegram_id)
            code = user.referral_code

        bot_username = self._get_bot_username()
        return f"https://t.me/{bot_username}?start=anon_{code}"

    def _get_bot_username(self) -> str:
        """دریافت username ربات.

        مقدار باید با یوزرنیم واقعی ربات در BotFather مطابقت داشته باشد.
        """
        return "SayaAnonBot"

    async def resolve_recipient(self, anon_code: str) -> int | None:
        """تبدیل کد ناشناس به شناسه‌ی تلگرام گیرنده.

        Args:
            anon_code: کد ناشناس استخراج‌شده از deep link (مثل SAYA-XXXX).

        Returns:
            شناسه‌ی تلگرام گیرنده یا None.
        """
        async with self._container.session() as session:
            user_repo = self._container.user_repo_with(session)
            user = await user_repo.get_by_referral_code(anon_code)
            if user is None:
                return None
            return user.telegram_id

    async def check_rate_limit(self, sender_telegram_id: int) -> bool:
        """بررسی محدودیت ارسال پیام ناشناس.

        Returns:
            True اگر مجاز است، False اگر محدود شده.
        """
        cutoff = datetime.now(UTC) - timedelta(hours=ANON_RATE_WINDOW_HOURS)
        async with self._container.session() as session:
            from sqlalchemy import func, select

            stmt = (
                select(func.count())
                .select_from(AnonymousMessage)
                .where(
                    AnonymousMessage.sender_telegram_id == sender_telegram_id,
                    AnonymousMessage.created_at >= cutoff,
                )
            )
            result = await session.execute(stmt)
            count = result.scalar_one()
        return count < ANON_RATE_LIMIT

    async def save_and_relay(
        self,
        bot: Bot,
        message: Message,
        *,
        recipient_telegram_id: int,
        sender_telegram_id: int,
    ) -> bool:
        """ذخیره‌ی پیام ناشناس و رله‌ی آن به گیرنده.

        Returns:
            True اگر موفق بود.
        """
        # بررسی Rate Limit
        if not await self.check_rate_limit(sender_telegram_id):
            return False

        # دریافت اطلاعات گیرنده
        async with self._container.session() as session:
            user_repo = self._container.user_repo_with(session)
            recipient = await user_repo.get_by_telegram_id(recipient_telegram_id)
            if recipient is None:
                return False
            recipient_db_id = recipient.id
            recipient_locale = recipient.language or "fa"

        # تشخیص نوع پیام و استخراج محتوا
        msg_type, text_content, file_id, file_unique_id = self._extract_content(message)

        # تولید نام نمایشی برای فرستنده ناشناس
        display_name = await self._get_next_display_name(recipient_db_id)

        # ذخیره در دیتابیس
        async with self._container.session() as session:
            anon_msg = AnonymousMessage(
                recipient_id=recipient_db_id,
                sender_telegram_id=sender_telegram_id,
                sender_display_name=display_name,
                message_type=msg_type,
                text_content=text_content,
                file_id=file_id,
                file_unique_id=file_unique_id,
                direction="in",
                is_read=False,
            )
            session.add(anon_msg)
            await session.flush()
            msg_id = anon_msg.id
            await session.commit()

        # ارسال به گیرنده
        try:
            from anonchat.i18n import t
            from anonchat.bot.keyboards import anon_message_keyboard

            header = (
                f"📩 <b>{t('anon_received', recipient_locale)}</b>\n"
                f"👤 <b>{display_name}</b>\n\n"
            )

            keyboard = anon_message_keyboard(recipient_locale, msg_id)

            tg_message = await self._send_to_recipient(
                bot,
                recipient_telegram_id,
                message,
                msg_type,
                text_content,
                file_id,
                header,
                keyboard,
            )

            # ذخیره telegram_message_id برای reply
            if tg_message is not None:
                async with self._container.session() as session:
                    from sqlalchemy import update

                    await session.execute(
                        update(AnonymousMessage)
                        .where(AnonymousMessage.id == msg_id)
                        .values(telegram_message_id=tg_message.message_id)
                    )
                    await session.commit()

            self._log.info(
                "anon.relayed",
                recipient=recipient_telegram_id,
                sender=sender_telegram_id,
                msg_id=msg_id,
                type=msg_type,
            )
            return True
        except Exception as exc:
            self._log.error(
                "anon.relay_failed",
                recipient=recipient_telegram_id,
                error=str(exc),
            )
            return False

    def _extract_content(self, message: Message) -> tuple[str, str | None, str | None, str | None]:
        """استخراج نوع و محتوای پیام."""
        from aiogram.enums import ContentType

        ct = message.content_type
        text = None
        file_id = None
        file_uid = None

        if ct == ContentType.TEXT:
            text = message.text
        elif ct == ContentType.PHOTO and message.photo:
            file_id = message.photo[-1].file_id
            file_uid = message.photo[-1].file_unique_id
            text = message.caption
        elif ct == ContentType.VIDEO and message.video:
            file_id = message.video.file_id
            file_uid = message.video.file_unique_id
            text = message.caption
        elif ct == ContentType.DOCUMENT and message.document:
            file_id = message.document.file_id
            file_uid = message.document.file_unique_id
            text = message.caption
        elif ct == ContentType.VOICE and message.voice:
            file_id = message.voice.file_id
            file_uid = message.voice.file_unique_id
        elif ct == ContentType.AUDIO and message.audio:
            file_id = message.audio.file_id
            file_uid = message.audio.file_unique_id
            text = message.caption
        elif ct == ContentType.ANIMATION and message.animation:
            file_id = message.animation.file_id
            file_uid = message.animation.file_unique_id
            text = message.caption
        elif ct == ContentType.VIDEO_NOTE and message.video_note:
            file_id = message.video_note.file_id
            file_uid = message.video_note.file_unique_id
        elif ct == ContentType.STICKER and message.sticker:
            file_id = message.sticker.file_id
            file_uid = message.sticker.file_unique_id

        type_map = {
            ContentType.TEXT: "text",
            ContentType.PHOTO: "photo",
            ContentType.VIDEO: "video",
            ContentType.DOCUMENT: "document",
            ContentType.VOICE: "voice",
            ContentType.AUDIO: "audio",
            ContentType.ANIMATION: "animation",
            ContentType.VIDEO_NOTE: "video_note",
            ContentType.STICKER: "sticker",
        }
        return type_map.get(ct, "text"), text, file_id, file_uid

    async def _send_to_recipient(
        self,
        bot: Bot,
        recipient_id: int,
        message: Message,
        msg_type: str,
        text: str | None,
        file_id: str | None,
        header: str,
        keyboard,
    ):
        """ارسال پیام به گیرنده بر اساس نوع."""
        full_text = f"{header}{text}" if text else header

        if msg_type == "text":
            return await bot.send_message(recipient_id, text=full_text, reply_markup=keyboard)
        elif msg_type == "photo":
            return await bot.send_photo(recipient_id, photo=file_id, caption=full_text, reply_markup=keyboard)
        elif msg_type == "video":
            return await bot.send_video(recipient_id, video=file_id, caption=full_text, reply_markup=keyboard)
        elif msg_type == "document":
            return await bot.send_document(recipient_id, document=file_id, caption=full_text, reply_markup=keyboard)
        elif msg_type == "voice":
            return await bot.send_voice(recipient_id, voice=file_id, caption=full_text, reply_markup=keyboard)
        elif msg_type == "audio":
            return await bot.send_audio(recipient_id, audio=file_id, caption=full_text, reply_markup=keyboard)
        elif msg_type == "animation":
            return await bot.send_animation(recipient_id, animation=file_id, caption=full_text, reply_markup=keyboard)
        elif msg_type == "video_note":
            # باگ: video_note از caption پشتیبانی نمی‌کند؛ هدر را جدا می‌فرستیم.
            await bot.send_message(recipient_id, text=header, reply_markup=keyboard)
            return await bot.send_video_note(recipient_id, video_note=file_id)
        elif msg_type == "sticker":
            await bot.send_message(recipient_id, text=header, reply_markup=keyboard)
            return await bot.send_sticker(recipient_id, sticker=file_id)
        return None

    async def _get_next_display_name(self, recipient_db_id: int) -> str:
        """تولید نام نمایشی بعدی برای فرستنده ناشناس (مثل «ناشناس #۵»)."""
        async with self._container.session() as session:
            from sqlalchemy import func, select

            stmt = (
                select(func.count())
                .select_from(AnonymousMessage)
                .where(
                    AnonymousMessage.recipient_id == recipient_db_id,
                    AnonymousMessage.direction == "in",
                )
            )
            result = await session.execute(stmt)
            count = result.scalar_one()
        return f"ناشناس #{count + 1}"

    async def reply_to_anon(
        self,
        bot: Bot,
        message: Message,
        *,
        anon_msg_id: int,
        sender_telegram_id: int,
    ) -> bool:
        """پاسخ صاحب لینک به یک پیام ناشناس.

        Args:
            anon_msg_id: شناسه‌ی پیام ناشناس در دیتابیس.
            sender_telegram_id: شناسه‌ی تلگرام صاحب لینک (پاسخ‌دهنده).
        """
        async with self._container.session() as session:
            from sqlalchemy import select

            stmt = select(AnonymousMessage).where(AnonymousMessage.id == anon_msg_id)
            result = await session.execute(stmt)
            original = result.scalar_one_or_none()
            if original is None:
                return False

            # دریافت اطلاعات فرستنده ناشناس اصلی
            anon_sender_tg = original.sender_telegram_id
            display_name = original.sender_display_name
            recipient_db_id = original.recipient_id

            msg_type, text_content, file_id, file_uid = self._extract_content(message)

            reply_msg = AnonymousMessage(
                recipient_id=recipient_db_id,
                sender_telegram_id=sender_telegram_id,
                sender_display_name="صاحب لینک",
                message_type=msg_type,
                text_content=text_content,
                file_id=file_id,
                file_unique_id=file_uid,
                direction="out",
                is_reply=True,
                reply_to_id=anon_msg_id,
            )
            session.add(reply_msg)
            await session.flush()
            await session.commit()

        # ارسال پاسخ به فرستنده ناشناس
        try:
            from anonchat.i18n import t

            header = f"💬 <b>{t('anon_reply_received')}</b>\n👤 پاسخ از صاحب لینک\n\n"

            if msg_type == "text":
                await bot.send_message(anon_sender_tg, text=f"{header}{text_content}")
            elif msg_type == "photo":
                await bot.send_photo(anon_sender_tg, photo=file_id, caption=f"{header}{text_content}")
            elif msg_type == "video":
                await bot.send_video(anon_sender_tg, video=file_id, caption=f"{header}{text_content}")
            elif msg_type == "document":
                await bot.send_document(anon_sender_tg, document=file_id, caption=f"{header}{text_content}")
            elif msg_type == "voice":
                await bot.send_voice(anon_sender_tg, voice=file_id, caption=header)
            elif msg_type == "audio":
                await bot.send_audio(anon_sender_tg, audio=file_id, caption=f"{header}{text_content}")
            elif msg_type == "animation":
                await bot.send_animation(anon_sender_tg, animation=file_id, caption=f"{header}{text_content}")
            elif msg_type == "sticker":
                await bot.send_message(anon_sender_tg, text=header)
                await bot.send_sticker(anon_sender_tg, sticker=file_id)
            elif msg_type == "video_note":
                # باگ: video_note از caption پشتیبانی نمی‌کند؛ هدر را جدا می‌فرستیم.
                await bot.send_message(anon_sender_tg, text=header)
                await bot.send_video_note(anon_sender_tg, video_note=file_id)

            self._log.info(
                "anon.replied",
                anon_msg=anon_msg_id,
                to_sender=anon_sender_tg,
            )
            return True
        except Exception as exc:
            self._log.error("anon.reply_failed", error=str(exc))
            return False

    async def forward_to_chat(
        self,
        bot: Bot,
        *,
        anon_msg_id: int,
        target_chat_id: int,
    ) -> bool:
        """فوروارد پیام ناشناس به یک کانال/گروه.

        Args:
            anon_msg_id: شناسه‌ی پیام ناشناس.
            target_chat_id: شناسه‌ی کانال/گروه مقصد.
        """
        async with self._container.session() as session:
            from sqlalchemy import select

            stmt = select(AnonymousMessage).where(AnonymousMessage.id == anon_msg_id)
            result = await session.execute(stmt)
            anon_msg = result.scalar_one_or_none()
            if anon_msg is None:
                return False

            msg_type = anon_msg.message_type
            text = anon_msg.text_content
            file_id = anon_msg.file_id

        try:
            header = f"📤 پیام ناشناس فوروارد‌شده\n👤 {anon_msg.sender_display_name}\n\n"

            if msg_type == "text":
                await bot.send_message(target_chat_id, text=f"{header}{text}")
            elif msg_type == "photo":
                await bot.send_photo(target_chat_id, photo=file_id, caption=f"{header}{text}")
            elif msg_type == "video":
                await bot.send_video(target_chat_id, video=file_id, caption=f"{header}{text}")
            elif msg_type == "document":
                await bot.send_document(target_chat_id, document=file_id, caption=f"{header}{text}")
            elif msg_type == "voice":
                await bot.send_voice(target_chat_id, voice=file_id, caption=header)
            elif msg_type == "audio":
                await bot.send_audio(target_chat_id, audio=file_id, caption=f"{header}{text}")
            elif msg_type == "animation":
                await bot.send_animation(target_chat_id, animation=file_id, caption=f"{header}{text}")
            elif msg_type == "sticker":
                await bot.send_message(target_chat_id, text=header)
                await bot.send_sticker(target_chat_id, sticker=file_id)
            elif msg_type == "video_note":
                # باگ: video_note از caption پشتیبانی نمی‌کند؛ هدر را جدا می‌فرستیم.
                await bot.send_message(target_chat_id, text=header)
                await bot.send_video_note(target_chat_id, video_note=file_id)

            # ثبت فوروارد
            async with self._container.session() as session:
                from sqlalchemy import update

                await session.execute(
                    update(AnonymousMessage)
                    .where(AnonymousMessage.id == anon_msg_id)
                    .values(forwarded_to_chat_id=target_chat_id)
                )
                await session.commit()

            self._log.info(
                "anon.forwarded",
                anon_msg=anon_msg_id,
                target=target_chat_id,
            )
            return True
        except Exception as exc:
            self._log.error("anon.forward_failed", error=str(exc))
            return False

    async def mark_as_read(self, anon_msg_id: int) -> None:
        """علامت‌گذاری پیام به‌عنوان خوانده‌شده."""
        async with self._container.session() as session:
            from sqlalchemy import update

            await session.execute(
                update(AnonymousMessage)
                .where(AnonymousMessage.id == anon_msg_id)
                .values(is_read=True)
            )
            await session.commit()

    async def get_user_anon_messages(
        self, telegram_id: int, *, limit: int = 20, unread_only: bool = False
    ) -> list[AnonymousMessage]:
        """دریافت لیست پیام‌های ناشناس کاربر."""
        async with self._container.session() as session:
            from sqlalchemy import select

            user_repo = self._container.user_repo_with(session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return []

            stmt = (
                select(AnonymousMessage)
                .where(
                    AnonymousMessage.recipient_id == user.id,
                    AnonymousMessage.direction == "in",
                )
                .order_by(AnonymousMessage.created_at.desc())
                .limit(limit)
            )
            if unread_only:
                stmt = stmt.where(AnonymousMessage.is_read.is_(False))

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_unread_count(self, telegram_id: int) -> int:
        """تعداد پیام‌های ناشناس خوانده‌نشده."""
        async with self._container.session() as session:
            from sqlalchemy import func, select

            user_repo = self._container.user_repo_with(session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return 0

            stmt = (
                select(func.count())
                .select_from(AnonymousMessage)
                .where(
                    AnonymousMessage.recipient_id == user.id,
                    AnonymousMessage.direction == "in",
                    AnonymousMessage.is_read.is_(False),
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one()
