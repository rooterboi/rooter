# 🎬 Kino Bot (aiogram 3.x + aiosqlite)

## Ishga tushirish
```bash
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # BOT_TOKEN va ADMIN_IDS ni to'ldiring
python main.py
```

## Arxitektura
```
main.py                  kirish nuqtasi
config.py                .env va default qiymatlar
database/db.py           aiosqlite (barcha SQL shu yerda)
handlers/                start, user, admin_*, rooter
keyboards/               user_kb, admin_kb
middlewares/user_mw.py   kontekst, foydalanuvchi qaydi, majburiy obuna
utils/                   bot_manager (multibot), cards, autopost, helpers, states
data/                    main.db va bot_<id>.db fayllari
```

## Multibot (Parent / Child)
- Bitta jarayon, bitta Dispatcher; har bir bot uchun alohida polling.
- Parent: `data/main.db` (+ `bots` jadvalida sub-botlar). Child: `data/bot_<id>.db` (alohida kino/foydalanuvchi bazasi).
- `is_parent=False` bo'lgani uchun sub-botda `/rooter` va "Sozlamalar" yo'q.

## Yashirin sub-bot
`/rooter` → PIN `9767` → bot tokeni. Buyruq nomi va PIN: **Admin panel → ⚙️ Sozlamalar** (faqat asosiy botda).
Sub-bot egasi o'sha botda avtomatik admin bo'ladi (`/admin`).

## Muhim
- Majburiy obuna va avto-post uchun botni kanalga **admin** qiling.
- FSM xotirada saqlanadi (qayta ishga tushganda jarayonlar tugaydi); xohlasangiz Redis storage ulang.
- Jarayon to'xtamasligi uchun systemd / pm2 / Docker ishlating.
