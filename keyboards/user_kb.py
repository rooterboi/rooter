"""Foydalanuvchi klaviaturalari."""
import math
from typing import Optional
from urllib.parse import quote

from aiogram.types import (InlineKeyboardButton as IB, InlineKeyboardMarkup as IM,
                           KeyboardButton as KB, ReplyKeyboardMarkup)

from config import PAGE_SIZE
from utils.helpers import chunk


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [[KB(text="🔍 Qidirish"), KB(text="🎭 Janrlar")],
            [KB(text="📅 Yillar"), KB(text="🔥 Top")],
            [KB(text="🆕 Yangilar"), KB(text="⭐ Saqlanganlar")]]
    if is_admin:
        rows.append([KB(text="👑 Admin panel")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def sub_kb(channels: list[dict], payload: str = "") -> IM:
    rows = [[IB(text=f"📢 {c['title'] or 'Kanal'}", url=c["link"])] for c in channels if c.get("link")]
    rows.append([IB(text="✅ Tekshirish", callback_data=f"check_sub:{payload[:40]}")])
    return IM(inline_keyboard=rows)


def item_kb(kind: str, row: dict, is_fav: bool, is_admin: bool, link: str) -> IM:
    iid = row["id"]
    rows = []
    if kind == "movie":
        rows.append([IB(text="▶️ Ko'rish / 📥 Yuklab olish", callback_data=f"watch:movie:{iid}")])
    else:
        rows.append([IB(text="📺 Qismlarni ko'rish", callback_data=f"seasons:{iid}")])
    rows.append([
        IB(text="💔 Saqlanganlardan olib tashlash" if is_fav else "❤️ Saqlash", callback_data=f"fav:{kind}:{iid}"),
        IB(text="🔗 Ulashish", url=f"https://t.me/share/url?url={quote(link, safe='')}"),
    ])
    rows.append([IB(text=f"{n}⭐", callback_data=f"rate:{kind}:{iid}:{n}") for n in range(1, 6)])
    if is_admin:
        rows.append([IB(text="✏️ Tahrirlash", callback_data=f"adm_edit:{kind}:{iid}"),
                     IB(text="🗑 O'chirish", callback_data=f"adm_del:{kind}:{iid}")])
        if kind == "series":
            rows.append([IB(text="➕ Qism qo'shish", callback_data=f"adm_epadd:{iid}"),
                         IB(text="📃 Qismlar", callback_data=f"adm_eps:{iid}")])
    return IM(inline_keyboard=rows)


def results_kb(results: list[dict], page: int, nav_prefix: str, back_cb: Optional[str] = None) -> IM:
    total = max(1, math.ceil(len(results) / PAGE_SIZE))
    page = min(max(page, 0), total - 1)
    rows = []
    for r in results[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]:
        icon = "🎬" if r["kind"] == "movie" else "📺"
        year = f" ({r['year']})" if r.get("year") else ""
        rows.append([IB(text=f"{icon} {r['title']}{year}", callback_data=f"open:{r['kind']}:{r['id']}")])
    if total > 1:
        nav = []
        if page > 0:
            nav.append(IB(text="◀️", callback_data=f"{nav_prefix}:{page - 1}"))
        nav.append(IB(text=f"{page + 1}/{total}", callback_data="noop"))
        if page < total - 1:
            nav.append(IB(text="▶️", callback_data=f"{nav_prefix}:{page + 1}"))
        rows.append(nav)
    if back_cb:
        rows.append([IB(text="◀️ Orqaga", callback_data=back_cb)])
    return IM(inline_keyboard=rows)


def genres_kb(genres: list[str]) -> IM:
    btns = [IB(text=g, callback_data=f"g:{g}") for g in genres if len(g.encode()) <= 55]
    return IM(inline_keyboard=chunk(btns, 2))


def years_kb(years: list[int]) -> IM:
    return IM(inline_keyboard=chunk([IB(text=str(y), callback_data=f"y:{y}") for y in years[:40]], 4))


def seasons_kb(series_id: int, seasons: list[dict]) -> IM:
    rows = [[IB(text=f"📂 {s['season']}-sezon ({s['cnt']} qism)", callback_data=f"season:{series_id}:{s['season']}")]
            for s in seasons]
    rows.append([IB(text="◀️ Serialga qaytish", callback_data=f"open:series:{series_id}")])
    return IM(inline_keyboard=rows)


def episodes_kb(series_id: int, episodes: list[dict], multi_season: bool) -> IM:
    btns = [IB(text=str(e["episode"]), callback_data=f"ep:{e['id']}") for e in episodes]
    rows = chunk(btns, 5)
    rows.append([IB(text="◀️ Orqaga", callback_data=f"seasons:{series_id}" if multi_season
                    else f"open:series:{series_id}")])
    return IM(inline_keyboard=rows)


def episode_kb(ep: dict, next_ep: Optional[dict], is_admin: bool) -> IM:
    rows = []
    if next_ep:
        rows.append([IB(text=f"▶️ Keyingi: {next_ep['episode']}-qism", callback_data=f"ep:{next_ep['id']}")])
    rows.append([IB(text="📋 Qismlar", callback_data=f"season:{ep['series_id']}:{ep['season']}"),
                 IB(text="📺 Serial", callback_data=f"open:series:{ep['series_id']}")])
    if is_admin:
        rows.append([IB(text="🗑 Qismni o'chirish", callback_data=f"adm_del:episode:{ep['id']}")])
    return IM(inline_keyboard=rows)
