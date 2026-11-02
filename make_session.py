import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"

async def main():
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        print("\n" + "="*30)
        print("YOUR_SESSION_START")
        print(client.session.save())
        print("YOUR_SESSION_END")
        print("="*30 + "\n")

if __name__ == '__main__':
    asyncio.run(main())
