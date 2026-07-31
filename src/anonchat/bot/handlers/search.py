"""هندلرهای جستجوی مخاطب و Matchmaking."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from anonchat.bot.keyboards import (
    cancel_keyboard,
    chat_keyboard,
    main_menu,
    search_criteria_keyboard,
)
from anonchat.bot.states.fsm import SearchStates
from anonchat.core.container import get_container
from anonchat.core.exceptions import (
    UserAlreadyInChatError,
    UserNotFoundError,
)
from anonchat.core.logging import get_logger
from anonchat.i18n import t
from anonchat.schemas.chat import SearchCriteriaDTO

router = Router()
_log = get_logger("handler.search")


@router.message(F.text.in_(["🔍 جستجوی مخاطب", "🔍 Find a partner"]))
async def start_search(message: Message, state: FSMContext) -> None:
    """شروع جستجوی مخاطب — نمایش معیارها."""
    container = get_container()
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(message.from_user.id)
        locale = getattr(db_user, "language", None) or "fa"
        is_registered = bool(db_user and db_user.is_registered)
        is_in_chat = bool(db_user and db_user.is_in_chat)

    if not is_registered:
        # باگ: در مسیر خطا state ممکن بود stale بماند؛ پاک می‌کنیم.
        await state.clear()
        await message.answer(t("error_not_registered", locale))
        return

    if is_in_chat:
        # باگ: در مسیر خطا state ممکن بود stale بماند؛ پاک می‌کنیم.
        await state.clear()
        await message.answer(t("error_already_in_chat", locale))
        return

    await state.set_state(SearchStates.choosing_criteria)
    await message.answer(
        t("search_criteria", locale),
        reply_markup=search_criteria_keyboard(locale),
    )


@router.callback_query(SearchStates.choosing_criteria, F.data == "search_random")
async def search_random(callback: CallbackQuery, state: FSMContext) -> None:
    """جستجوی تصادفی."""
    await _perform_search(callback, state, SearchCriteriaDTO())


@router.callback_query(SearchStates.choosing_criteria, F.data == "search_gender")
async def search_by_gender(callback: CallbackQuery, state: FSMContext) -> None:
    """جستجو بر اساس جنسیت — نیاز به ورودی."""
    locale = "fa"
    try:
        await state.set_state(SearchStates.waiting_gender_pref)
        await callback.message.answer(  # type: ignore[attr-defined]
            "جنسیت مورد نظر را بنویسید (male/female/other):",
            reply_markup=cancel_keyboard(locale),
        )
    finally:
        try:
            await callback.answer()
        except Exception:
            pass


@router.callback_query(SearchStates.choosing_criteria, F.data == "search_country")
async def search_by_country(callback: CallbackQuery, state: FSMContext) -> None:
    """جستجو بر اساس کشور."""
    try:
        await state.set_state(SearchStates.waiting_country_pref)
        await callback.message.answer(  # type: ignore[attr-defined]
            "کد کشور مورد نظر را وارد کنید (مثل IR, US):",
            reply_markup=cancel_keyboard("fa"),
        )
    finally:
        try:
            await callback.answer()
        except Exception:
            pass


@router.callback_query(SearchStates.choosing_criteria, F.data == "search_language")
async def search_by_language(callback: CallbackQuery, state: FSMContext) -> None:
    """جستجو بر اساس زبان."""
    try:
        await state.set_state(SearchStates.waiting_language_pref)
        await callback.message.answer(  # type: ignore[attr-defined]
            "کد زبان مورد نظر را وارد کنید (مثل fa, en):",
            reply_markup=cancel_keyboard("fa"),
        )
    finally:
        try:
            await callback.answer()
        except Exception:
            pass


@router.callback_query(SearchStates.choosing_criteria, F.data == "search_age")
async def search_by_age(callback: CallbackQuery, state: FSMContext) -> None:
    """جستجو بر اساس بازه سنی."""
    try:
        await state.set_state(SearchStates.waiting_age_range)
        await callback.message.answer(  # type: ignore[attr-defined]
            "بازه سنی مورد نظر را وارد کنید (مثال: 18-30):",
            reply_markup=cancel_keyboard("fa"),
        )
    finally:
        try:
            await callback.answer()
        except Exception:
            pass


@router.message(SearchStates.waiting_gender_pref)
async def process_gender_pref(message: Message, state: FSMContext) -> None:
    gender = (message.text or "").strip().lower()
    if gender not in ("male", "female", "other"):
        await message.answer("ورودی نامعتبر. male/female/other را وارد کنید.")
        return
    await _perform_search_message(message, state, SearchCriteriaDTO(gender=gender))  # type: ignore[arg-type]


@router.message(SearchStates.waiting_country_pref)
async def process_country_pref(message: Message, state: FSMContext) -> None:
    from anonchat.core.security import validate_country_code
    try:
        country = validate_country_code(message.text or "")
    except ValueError:
        await message.answer("کد کشور نامعتبر.")
        return
    await _perform_search_message(message, state, SearchCriteriaDTO(country=country))


@router.message(SearchStates.waiting_language_pref)
async def process_language_pref(message: Message, state: FSMContext) -> None:
    from anonchat.core.security import validate_language_code
    try:
        lang = validate_language_code(message.text or "")
    except ValueError:
        await message.answer("کد زبان نامعتبر.")
        return
    await _perform_search_message(message, state, SearchCriteriaDTO(language=lang))


@router.message(SearchStates.waiting_age_range)
async def process_age_pref(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    try:
        parts = text.split("-")
        if len(parts) != 2:
            raise ValueError
        age_min, age_max = int(parts[0]), int(parts[1])
    except (ValueError, TypeError):
        await message.answer("فرمت نامعتبر. مثال صحیح: 18-30")
        return
    await _perform_search_message(
        message, state, SearchCriteriaDTO(age_min=age_min, age_max=age_max)
    )


async def _perform_search(callback: CallbackQuery, state: FSMContext, criteria: SearchCriteriaDTO) -> None:
    """انجاد جستجو از callback."""
    container = get_container()
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(callback.from_user.id)
        locale = getattr(db_user, "language", None) or "fa"

    # ویرایش پیام قبلی یا ارسال پیام جدید در صورت خطا
    try:
        await callback.message.edit_text(t("search_started", locale))  # type: ignore[attr-defined]
    except Exception:
        await callback.message.answer(t("search_started", locale))  # type: ignore[attr-defined]

    # matchmaking را در try/finally بپیچ تا callback.answer همیشه صدا زده شود
    try:
        await _do_matchmaking(callback.message, callback.from_user.id, locale, criteria, state)  # type: ignore[attr-defined]
    finally:
        # مهم: callback.answer باید همیشه صدا زده شود تا تلگرام دکمه را
        # از حالت «در حال چرخش» خارج کند. اگر صدا زده نشود، کاربر فکر
        # می‌کند دکمه کار نمی‌کند.
        try:
            await callback.answer()
        except Exception:
            pass


async def _perform_search_message(message: Message, state: FSMContext, criteria: SearchCriteriaDTO) -> None:
    """انجام جستجو از message."""
    container = get_container()
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(message.from_user.id)
        locale = getattr(db_user, "language", None) or "fa"

    await message.answer(t("search_started", locale))
    await _do_matchmaking(message, message.from_user.id, locale, criteria, state)


async def _do_matchmaking(
    message: Message,
    telegram_id: int,
    locale: str,
    criteria: SearchCriteriaDTO,
    state: FSMContext,
) -> None:
    """اجرای الگوریتم matchmaking."""
    container = get_container()
    try:
        partner_tg_id, session_id = await container.matchmaking_service.start_search(
            telegram_id, criteria
        )
    except UserAlreadyInChatError:
        await message.answer(t("error_already_in_chat", locale))
        await state.clear()
        return
    except UserNotFoundError:
        await message.answer(t("error_not_registered", locale))
        await state.clear()
        return
    except Exception as exc:
        _log.error("search.failed", user_id=telegram_id, error=str(exc))
        await message.answer(t("error_generic", locale))
        await state.clear()
        return

    await state.clear()

    if partner_tg_id is None:
        # وارد صف شد
        await message.answer(t("search_no_partner", locale), reply_markup=cancel_keyboard(locale))
        await state.set_state(SearchStates.in_queue)
        return

    # مچ پیدا شد
    await message.answer(
        t("search_matched", locale),
        reply_markup=chat_keyboard(locale),
    )

    # اطلاع به شریک
    bot = message.bot
    if bot is not None:
        try:
            # یافتن زبان شریک
            async with container.session() as session:
                user_repo = container.user_repo_with(session)
                partner_user = await user_repo.get_by_telegram_id(partner_tg_id)
                partner_locale = getattr(partner_user, "language", None) or "fa"
            await bot.send_message(
                partner_tg_id,
                t("search_partner_connected", partner_locale),
                reply_markup=chat_keyboard(partner_locale),
            )
        except Exception as exc:
            _log.error("search.notify_partner_failed", error=str(exc))

    # پاداش XP
    await container.user_service.add_xp(telegram_id, 2)


async def _do_cancel_search(target_message: Message, telegram_id: int, state: FSMContext) -> None:
    """لغو جستجو — منطق مشترک برای Message و CallbackQuery."""
    container = get_container()
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(telegram_id)
        locale = getattr(db_user, "language", None) or "fa"

    await container.matchmaking_service.cancel_search(telegram_id)
    await state.clear()

    await target_message.answer(
        t("search_cancelled", locale),
        reply_markup=main_menu(locale),
    )


@router.callback_query(F.data == "cancel_search")
async def cancel_search_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """لغو جستجو از دکمه‌ی اینلاین."""
    await _do_cancel_search(callback.message, callback.from_user.id, state)  # type: ignore[arg-type]
    await callback.answer()


# نکته: لغو از دکمه‌ی ریپلای کیبورد («❌ لغو») توسط cmd_cancel در start.py
# هندل می‌شود که آن هم matchmaking_service.cancel_search را صدا می‌زند.
