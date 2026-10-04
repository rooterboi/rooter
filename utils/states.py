"""FSM holatlari."""
from aiogram.fsm.state import State, StatesGroup


class AddItem(StatesGroup):      # kino / serial qo'shish
    video = State()
    poster = State()
    fields = State()


class AddEpisode(StatesGroup):   # serialga qism qo'shish
    season = State()
    episode = State()
    video = State()
    code = State()


class FindItem(StatesGroup):     # kod bo'yicha topish (tahrirlash/o'chirish/qism)
    code = State()


class EditItem(StatesGroup):
    value = State()


class ChannelSt(StatesGroup):
    add = State()


class BroadcastSt(StatesGroup):
    content = State()
    confirm = State()


class SettingsSt(StatesGroup):
    rooter_cmd = State()
    rooter_pin = State()
    add_admin = State()


class RooterSt(StatesGroup):
    pin = State()
    token = State()
