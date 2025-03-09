from aiogram import Bot
import io
import asyncio

BOT_TOKEN = "ТВОЙ_ТОКЕН"
CHAT_ID = "ТВОЙ_CHAT_ID"

async def test_send_file():
    bot = Bot(token=BOT_TOKEN)

    # Простой код для теста
    game_code = "print('Hello, Test!')"

    # Создаём виртуальный файл в памяти
    file_buffer = io.BytesIO()
    file_buffer.write(game_code.encode('utf-8'))
    file_buffer.seek(0)

    await bot.send_document(
        document=file_buffer,
        caption="Тестовый файл .py",
        filename="test_game.py"
    )

    await bot.session.close()

asyncio.run(test_send_file())
