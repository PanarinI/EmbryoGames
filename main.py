import logging
from openai import OpenAI
import asyncio
import os
import io
import subprocess
from dotenv import load_dotenv
from aiogram import types
from aiogram import Bot, Dispatcher, types, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command  # Добавьте этот импорт
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import StateFilter

import config

# Загрузка переменных окружения из .env
load_dotenv()

# Инициализация бота и диспетчера
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env file")

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()  # Создание маршрутизатора

# Логирование
logging.basicConfig(level=logging.INFO)



# Клавиатура главного меню
def main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Сгенерировать игру', callback_data='generate_game')],
        [InlineKeyboardButton(text='Помощь', callback_data='help')]
    ])
    return keyboard

# Состояния для FSM
class GameState(StatesGroup):
    waiting_for_prompt = State()
    waiting_for_exe_request = State()  # Добавлено корректное состояние

# Команда /start
@router.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer('Добро пожаловать в EmbryoGames! Выберите действие:', reply_markup=main_menu_keyboard())


# Обработка нажатий кнопок
@router.callback_query(lambda c: c.data == 'generate_game')
async def process_generate_game(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(GameState.waiting_for_prompt)
    await bot.send_message(callback_query.from_user.id, 'Введите промпт для генерации игры:')


@router.callback_query(lambda c: c.data == 'help')
async def process_help(callback_query: CallbackQuery):
    await bot.send_message(callback_query.from_user.id,
                           'EmbryoGames - игры в зародыше. Введите промпт и получите уникальный игровой прототип!')


# Обработка ввода промпта
@router.message(StateFilter(GameState.waiting_for_prompt))
async def handle_prompt(message: types.Message, state: FSMContext):
    prompt = message.text
    await message.answer('Генерирую игру... Пожалуйста, подождите.')

    prompt = f'''Создай компьютерную игру на Pygame в один Python файл.
            Идею возьми из prompt и придумай как обыграть эту идею в простой, но самобытной механике.
            Только код! Не добавляй описание, комментарии или объяснения.
            В коде должны соблюдаться следующие условия:
            1. Код игры должен запускаться.
            2. Игра имеет цель, и эта цель достижима
            3. Если указаны персонажи - они должны быть реализованы в игре.
            3. В игре можно проиграть.
            4. В игре можно выиграть.
            5. На экране игры должно отображаться название игры, краткое описание игры и иронично-ворчливая приписка, во что можно было бы превратить игру, если бы кто-нибудь взялся разрабатывать, и управление.

            Убедись, что игра действительно работает. У тебя есть только одна попытка
            Используй максимум 3000 токенов.

            Основная идея игры: {prompt}

            Выводи только код в формате:

            ```python
            # здесь начинается код
            import pygame
            ...
            # здесь заканчивается код
            ```'''

    try:
        response = client.chat.completions.create(
            model=config.MODEL,
            messages=[
                {"role": "system", "content": "You are a game developer."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=config.MAX_TOKENS,
            temperature=config.TEMPERATURE,
        )

        if response.choices and len(response.choices) > 0:
            game_code = response.choices[0].message.content

            # Извлечение кода из блока ```python ... ```
            if "```python" in game_code:
                game_code = game_code.split("```python")[1].split("```")[0].strip()

                # Создание .py файла в памяти
                py_buffer = io.BytesIO()
                py_buffer.write(game_code.encode('utf-8'))
                py_buffer.seek(0)

                # Отправка .py файла пользователю
                py_document = BufferedInputFile(py_buffer.read(), filename="embryo_game.py")
                await bot.send_document(
                    chat_id=message.chat.id,
                    document=py_document,
                    caption="Сгенерированный .py файл:",
                    reply_markup=exe_request_keyboard()  # Добавляем клавиатуру с кнопкой
                )

                # Логирование перед обновлением данных FSM
                logging.info(f"Перед сохранением в FSM: game_code длина = {len(game_code)}")

                # Сохраняем содержимое game_code в состояние FSM для дальнейшего использования
                await state.update_data(game_code=game_code)

                # Логирование данных после сохранения
                state_data = await state.get_data()
                logging.info(f"Сохранённый game_code в FSM: {state_data.get('game_code')}")

                await state.set_state(GameState.waiting_for_exe_request)

            else:
                await message.answer("Ошибка при генерации игры. Попробуйте еще раз.")

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer(f"Ошибка при генерации игры: {e}")


@router.callback_query(lambda c: c.data == 'generate_exe')
async def handle_generate_exe(callback_query: CallbackQuery, state: FSMContext):
    await bot.send_message(callback_query.from_user.id, "Начинаю компиляцию .exe файла... Пожалуйста, подождите.")

    # Получение данных из состояния FSM
    state_data = await state.get_data()
    game_code = state_data.get("game_code")

    # Логирование данных из FSM перед использованием
    logging.info(f"Полученный game_code из FSM: {game_code}")

    if not game_code:
        await bot.send_message(callback_query.from_user.id,
                               "Ошибка: код игры не найден. Попробуйте заново сгенерировать .py файл.")
        return

    try:
        # Создание временного .py файла на диске для PyInstaller
        with open("embryo_game.py", "w", encoding="utf-8") as temp_py_file:
            temp_py_file.write(game_code)

        # Сборка exe через PyInstaller в один файл без консоли
        subprocess.run([
            "pyinstaller",
            "--onefile",
            "--noconsole",
            "embryo_game.py"
        ], check=True)

        exe_path = os.path.join("dist", "embryo_game.exe")

        # Чтение .exe файла в виртуальный буфер
        exe_buffer = io.BytesIO()
        with open(exe_path, "rb") as exe_file:
            exe_buffer.write(exe_file.read())

        exe_buffer.seek(0)

        # Отправка .exe файла пользователю
        exe_document = BufferedInputFile(exe_buffer.read(), filename="embryo_game.exe")
        await bot.send_document(
            chat_id=callback_query.from_user.id,
            document=exe_document,
            caption="Сгенерированный .exe файл:"
        )

        # Удаление временных файлов и директорий после отправки
        for folder in ["build", "dist"]:
            if os.path.exists(folder):
                subprocess.run(["rm", "-rf", folder], shell=True)

        for file in ["embryo_game.spec", "embryo_game.py"]:
            if os.path.exists(file):
                os.remove(file)

    except Exception as e:
        logging.error(f"Ошибка при создании .exe файла: {e}")
        await bot.send_message(callback_query.from_user.id, f"Ошибка при создании .exe файла: {e}")

    await state.clear()

# Клавиатура для генерации .exe файла
def exe_request_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Создать .exe прямо здесь, чтобы можно было сыграть?', callback_data='generate_exe')]
    ])
    return keyboard

# Основная асинхронная функция для запуска бота
async def main():
    dp.include_router(router)  # Подключение маршрутизатора к диспетчеру
    await dp.start_polling(bot)


# Запуск бота
if __name__ == "__main__":
    asyncio.run(main())