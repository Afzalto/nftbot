import asyncio
import json
from pathlib import Path
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.client.bot import DefaultBotProperties
from catalog import catalog, category_names


from catalog import category_names, catalog as initial_catalog

TOKEN = "7238684986:AAH_A8GoW47TY0UVSsfej-kkLQZdia1uMWI"
ADMINS = ["afzalto", "asck11"]

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

DATA_FILE = Path("catalog_data.json")

# Загружаем каталог из файла, если есть, иначе из catalog.py
def load_catalog():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            print("Ошибка загрузки catalog_data.json:", e)
    return initial_catalog.copy()

# Сохраняем каталог в JSON
def save_catalog(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print("Каталог сохранён.")
    except Exception as e:
        print("Ошибка сохранения каталога:", e)

catalog = load_catalog()

class AddGiftState(StatesGroup):
    choosing_category = State()
    entering_name = State()
    entering_price = State()
    entering_link = State()

# Храним список ID отправленных сообщений
user_sent_messages = {}

@dp.message(F.text == "/start")
async def start(message: Message):
    await send_catalog(message)

async def send_catalog(target):
    kb = InlineKeyboardBuilder()
    for cat_id, name in category_names.items():
        kb.add(InlineKeyboardButton(text=name, callback_data=f"cat:{cat_id}"))
    kb.adjust(2)
    await target.answer("Выбери категорию подарков:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("cat:"))
async def show_products(callback: CallbackQuery):
    global catalog
    catalog = load_catalog()  # загружаем свежие данные из JSON

    cat_id = callback.data.split(":")[1]
    products = catalog.get(cat_id, [])
    
    await callback.message.delete()

    # Очистим старые сообщения пользователя (если есть)
    old_messages = user_sent_messages.get(callback.from_user.id, [])
    for msg_id in old_messages:
        try:
            await callback.bot.delete_message(callback.message.chat.id, msg_id)
        except:
            pass  # сообщение могло быть уже удалено

    sent_ids = []

    if not products:
        msg = await callback.message.answer("🎁 Товары не найдены в этой категории.")
        sent_ids.append(msg.message_id)
    else:
        for item in products:
            text = f"<b>{item['name']}</b>\nЦена: {item['price']}"
            button = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🛍 Купить", url=item["link"])
            ]])
            msg = await callback.message.answer(text, reply_markup=button)
            sent_ids.append(msg.message_id)

    # Кнопка вернуться
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Вернуться в каталог", callback_data="back_to_catalog")
    ]])
    msg = await callback.message.answer("⬇️ Выбери другую категорию:", reply_markup=back_kb)
    sent_ids.append(msg.message_id)

    # Сохраняем отправленные ID
    user_sent_messages[callback.from_user.id] = sent_ids
    await callback.answer()

@dp.callback_query(F.data == "back_to_catalog")
async def back_to_catalog(callback: CallbackQuery):
    # Удаляем старые сообщения
    old_messages = user_sent_messages.get(callback.from_user.id, [])
    for msg_id in old_messages:
        try:
            await callback.bot.delete_message(callback.message.chat.id, msg_id)
        except:
            pass
    user_sent_messages[callback.from_user.id] = []

    await send_catalog(callback.message)
    await callback.answer()

@dp.message(F.text == "/add_gift")
async def add_gift_start(message: Message, state: FSMContext):
    if not message.from_user.username or message.from_user.username.lower() not in ADMINS:
        await message.answer("❌ У тебя нет доступа к этой команде.")
        return
    kb = InlineKeyboardBuilder()
    for cat_id, name in category_names.items():
        kb.add(InlineKeyboardButton(text=name, callback_data=f"add_cat:{cat_id}"))
    kb.adjust(2)
    await message.answer("Выбери категорию для добавления подарка:", reply_markup=kb.as_markup())
    await state.set_state(AddGiftState.choosing_category)

@dp.callback_query(F.data.startswith("add_cat:"), AddGiftState.choosing_category)
async def choose_category(callback: CallbackQuery, state: FSMContext):
    cat_id = callback.data.split(":")[1]
    await state.update_data(cat_id=cat_id)
    await callback.message.answer("Введи название подарка:")
    await state.set_state(AddGiftState.entering_name)
    await callback.answer()

@dp.message(AddGiftState.entering_name)
async def enter_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Теперь введи цену подарка (числом):")
    await state.set_state(AddGiftState.entering_price)

@dp.message(AddGiftState.entering_price)
async def enter_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Цена должна быть числом. Попробуй ещё раз.")
        return
    await state.update_data(price=int(message.text))
    await message.answer("Введи ссылку на подарок:")
    await state.set_state(AddGiftState.entering_link)

@dp.message(AddGiftState.entering_link)
async def enter_link(message: Message, state: FSMContext):
    data = await state.get_data()
    cat_id = data["cat_id"]
    name = data["name"]
    price = data["price"]
    link = message.text

    new_gift = {"name": name, "price": price, "link": link}
    catalog.setdefault(cat_id, []).append(new_gift)
    save_catalog(catalog)

    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🔙 Вернуться в каталог", callback_data="back_to_catalog"))

    await message.answer(f"✅ Подарок '{name}' добавлен в категорию {category_names.get(cat_id, 'неизвестная')}!", reply_markup=kb.as_markup())
    await state.clear()

@dp.message(F.text == "/remove_gift")
async def remove_gift_cmd(message: Message):
    if not message.from_user.username or message.from_user.username.lower() not in ADMINS:
        return await message.answer("❌ У тебя нет прав для удаления подарков.")

    kb = InlineKeyboardBuilder()
    for cat_id, cat_name in category_names.items():
        kb.add(InlineKeyboardButton(text=cat_name, callback_data=f"rmcat:{cat_id}"))
    kb.adjust(2)
    await message.answer("Выбери категорию для удаления подарка:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("rmcat:"))
async def remove_gift_choose(callback: CallbackQuery):
    cat_id = callback.data.split(":")[1]
    gifts = catalog.get(cat_id, [])
    if not gifts:
        return await callback.message.edit_text("❌ В этой категории нет подарков.")

    kb = InlineKeyboardBuilder()
    for i, gift in enumerate(gifts):
        kb.add(InlineKeyboardButton(
            text=f"{gift['name']}",
            callback_data=f"rmgift:{cat_id}:{i}"
        ))
    kb.adjust(1)

    await callback.message.edit_text(
        f"Подарки в категории {category_names.get(cat_id, 'неизвестная')} (нажми на подарок, чтобы удалить):",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(F.data.startswith("rmgift:"))
async def remove_gift(callback: CallbackQuery):
    _, cat_id, index_str = callback.data.split(":")
    index = int(index_str)

    try:
        removed = catalog[cat_id].pop(index)
        if not catalog[cat_id]:
            del catalog[cat_id]
        save_catalog(catalog)

        kb = InlineKeyboardBuilder()
        kb.add(InlineKeyboardButton(text="🔙 Вернуться в каталог", callback_data="back_to_catalog"))

        await callback.message.edit_text(f"✅ Подарок удалён: {removed['name']}", reply_markup=kb.as_markup())
    except Exception as e:
        await callback.message.edit_text("❌ Не удалось удалить подарок.")

@dp.callback_query(F.data == "back_to_catalog")
async def back_to_catalog(callback: CallbackQuery):
    kb = InlineKeyboardBuilder()
    for cat_id, name in category_names.items():
        kb.add(InlineKeyboardButton(text=name, callback_data=f"add_cat:{cat_id}"))
    kb.adjust(2)
    await callback.message.edit_text("Выбери категорию:", reply_markup=kb.as_markup())
async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


