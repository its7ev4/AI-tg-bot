from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart


user = Router()


@user.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer('Добро пожаловать!')