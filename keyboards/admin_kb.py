"""Admin panel klaviaturalari."""
from aiogram.types import InlineKeyboardButton as IB, InlineKeyboardMarkup as IM

CANCEL = IB(text="❌ Bekor qilish", callback_data="adm:cancel")


def admin_menu(is_parent: bool) -> IM:
    rows = [
        [IB(text="🎬 Kinolar", callback_data="adm:movies"), IB(text="📺 Seriallar", callback_data="adm:series")],
        [IB(text="📢 Majburiy obuna", callback_data="adm:ch:sub"), IB(text="📡 Avto-post", callback_data="adm:ch:post")],
        [IB(text="📊 Statistika", callback_data="adm:stats"), IB(text="✉️ Rassilka", callback_data="adm:bc")],
        [IB(text="👥 Adminlar", callback_data="adm:admins")],
    ]
    if is_parent:
        rows.append([IB(text="⚙️ Sozlamalar", callback_data="adm:settings")])
    rows.append([IB(text="✖️ Yopish", callback_data="adm:close")])
    return IM(inline_keyboard=rows)


def movies_menu() -> IM:
    return IM(inline_keyboard=[
        [IB(text="➕ Kino qo'shish", callback_data="adm:add:movie")],
        [IB(text="✏️ Tahrirlash", callback_data="adm:find:edit"), IB(text="🗑 O'chirish", callback_data="adm:find:del")],
        [IB(text="📋 Ro'yxat", callback_data="adm:list:movie:0")],
        [IB(text="◀️ Orqaga", callback_data="adm:home")]])


def series_menu() -> IM:
    return IM(inline_keyboard=[
        [IB(text="➕ Serial yaratish", callback_data="adm:add:series")],
        [IB(text="🎞 Qism qo'shish", callback_data="adm:find:epadd"), IB(text="📃 Qismlar", callback_data="adm:find:eps")],
        [IB(text="✏️ Tahrirlash", callback_data="adm:find:edit"), IB(text="🗑 O'chirish", callback_data="adm:find:del")],
        [IB(text="📋 Ro'yxat", callback_data="adm:list:series:0")],
        [IB(text="◀️ Orqaga", callback_data="adm:home")]])


def cancel_kb() -> IM:
    return IM(inline_keyboard=[[CANCEL]])


def field_kb(key: str, required: bool) -> IM:
    rows = []
    if key == "code":
        rows.append([IB(text="🔢 Avto kod", callback_data="af:auto")])
    if not required:
        rows.append([IB(text="⏭ O'tkazib yuborish", callback_data="af:skip")])
    rows.append([CANCEL])
    return IM(inline_keyboard=rows)


def skip_kb() -> IM:
    return IM(inline_keyboard=[[IB(text="⏭ O'tkazib yuborish", callback_data="af:skip")], [CANCEL]])


def edit_kb(kind: str, iid: int) -> IM:
    fields = [("title", "📝 Nomi"), ("code", "🔑 Kodi"), ("genre", "🎭 Janr"), ("year", "🗓 Yil"),
              ("lang", "🌐 Til"), ("quality", "💿 Sifat"), ("description", "📄 Tavsif"), ("poster", "🖼 Poster")]
    if kind == "movie":
        fields.append(("file_id", "🎥 Video"))
    btns = [IB(text=t, callback_data=f"ef:{kind}:{iid}:{f}") for f, t in fields]
    rows = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    rows.append([CANCEL])
    return IM(inline_keyboard=rows)


def confirm_del_kb(kind: str, iid: int) -> IM:
    return IM(inline_keyboard=[[IB(text="✅ Ha, o'chirish", callback_data=f"adm_delok:{kind}:{iid}"),
                                IB(text="❌ Yo'q", callback_data="adm:cancel")]])
