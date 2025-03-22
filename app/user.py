from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

import app.keyboards as kb
from app.states import Chat, Image
from app.generators import gpt_text, gpt_image, gpt_vision
from app.database.requests import set_user, get_user, calculate
from decimal import Decimal
import uuid
import os


user = Router()

@user.message(F.text == 'Назад')
@user.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    current_state = await state.get_state()
    
    # Проверяем, если текущее состояние не пустое, значит, пользователь уже в чате
    if current_state:
        await state.clear()  # Сбрасываем состояние
        await message.answer('Вы вышли из текущего режима.', reply_markup=kb.main)
    else:
        await set_user(message.from_user.id)
        await message.answer('Добро пожаловать!', reply_markup=kb.main)
    
    # Сбрасываем состояние независимо от того, был ли пользователь в чате
    await state.clear()


@user.message(F.text == 'Чат')
async def chatting(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if Decimal(user.balance) > 0:
        await state.set_state(Chat.text)
        await message.answer('Введите ваш запрос.', reply_markup=kb.cancel)
    else:
        await message.answer('Недостаточно средств на балансе.')


@user.message(Chat.text, F.photo)
async def chat_response(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if Decimal(user.balance) > 0:
        await state.set_state(Chat.wait)
        file = await message.bot.get_file(message.photo[-1].file_id)
        file_path = file.file_path
        file_name = f"{uuid.uuid4()}.jpeg"  # Генерируем имя файла с расширением
        
        # Логируем путь файла для проверки
        print(f"Downloading file from: {file_path}")
        
        # Проверяем caption
        caption = message.caption if message.caption else "Без описания"  # Подставляем текст по умолчанию
        try:
            await message.bot.download_file(file_path, file_name)  # Скачиваем файл
            print(f"File downloaded successfully: {file_name}")
            
            # Передаем файл как base64
            response = await gpt_vision(caption, 'gpt-4o', file_name)
            await calculate(message.from_user.id, response['usage'], 'gpt-4o', user)
            print(f"Response from gpt_vision: {response}")
            
            if 'response' in response:
                await message.answer(response['response'])
            else:
                await message.answer("Извините, не удалось обработать ваш запрос. Попробуйте немного изменить текст и отправить снова.")
        except Exception as e:
            print(f"Error during file processing: {e}")
            await message.answer("Произошла ошибка при обработке изображения. Попробуйте снова.")
        finally:
            if os.path.exists(file_name):
                os.remove(file_name)  # Удаляем файл после обработки
        await state.set_state(Chat.text)
    else:
        await message.answer('Недостаточно средств на балансе.')


@user.message(Image.wait)
@user.message(Chat.wait)
async def wait_wait(message: Message):
    await message.answer('Ваше сообщение обрабатывается, пожалуйста, подождите.')


@user.message(F.text == 'Генерация картинок')
async def chatting(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if Decimal(user.balance) > 0:
        await state.set_state(Image.text)
        await message.answer('Введите ваш запрос.', reply_markup=kb.cancel)
    else:
        await message.answer('Недостаточно средств на балансе.')


@user.message(Image.text)
async def chat_response(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if Decimal(user.balance) > 0:
        try:
            await state.set_state(Image.wait)
            print(f"Received text for image generation: {message.text}")  # Логируем текст

            # Генерация изображения через OpenAI
            response = await gpt_image(message.text, 'dall-e-3')

            # Проверка успешности ответа от OpenAI
            if 'response' in response:
                await message.answer_photo(photo=response['response'])
            else:
                # Если не получилось получить результат
                await message.answer("Извините, не удалось обработать ваш запрос. Попробуйте немного изменить текст и отправить снова.")
                print(f"Error: No valid response from OpenAI for image generation.")
        except Exception as e:
            print(f"Error during image generation: {e}")
            await message.answer("Произошла ошибка при обработке вашего запроса. Опишите желаемую картинку конкретнее.")
        finally:
            await state.set_state(Image.text)
    else:
        await message.answer('Недостаточно средств на балансе.')


@user.message(Chat.text)
async def chat_response(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if Decimal(user.balance) > 0:
        await state.set_state(Chat.wait)
        
        # Обрабатываем текстовый запрос через gpt_text
        response = await gpt_text(message.text, 'gpt-4o')
        
        await calculate(message.from_user.id, response['usage'], 'gpt-4o', user)
        print(f"Response from gpt_text: {response}")
        
        try:
            if 'response' in response:
                await message.answer(response['response'])
            else:
                await message.answer("Извините, не удалось обработать ваш запрос. Попробуйте немного изменить текст и отправить снова.")
        except Exception as e:
            print(f"Error while sending text response: {e}")
            await message.answer("Произошла ошибка при отправке текста. Попробуйте снова.")
        
        await state.set_state(Chat.text)
    else:
        await message.answer('Недостаточно средств на балансе.')
