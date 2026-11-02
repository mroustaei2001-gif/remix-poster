import os
import asyncio
import re
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeAudio
from pydub import AudioSegment
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, COMM, APIC

# --- متغیرهای محیطی دریافتی از Railway ---
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
STRING_SESSION = os.getenv('STRING_SESSION', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

TARGET_CHANNEL = os.getenv('TARGET_CHANNEL', '')
POST_INTERVAL = int(os.getenv('POST_INTERVAL', '10800'))

# کانال‌های منبع برای برداشتن موزیک
SOURCE_CHANNELS = [
    'SourceChannel1',
    'SourceChannel2',
    'SourceChannel3'
]

COVER_PATH = "cover.png"

user_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

MUSIC_QUEUE = []
PROCESSED_TRACKS = set()

def update_metadata_and_cover(file_path, title, artist, cover_file):
    try:
        audio = MP3(file_path, ID3=ID3)
        try:
            audio.add_tags()
        except Exception:
            pass

        audio.tags.add(TIT2(encoding=3, text=title))
        audio.tags.add(TPE1(encoding=3, text=artist))
        audio.tags.add(COMM(encoding=3, lang='eng', desc='', text=f't.me/{TARGET_CHANNEL.replace("@", "")}'))

        if os.path.exists(cover_file):
            with open(cover_file, 'rb') as img:
                audio.tags.add(APIC(
                    encoding=3,
                    mime='image/png',
                    type=3,
                    desc='Cover',
                    data=img.read()
                ))

        audio.save(v2_version=3)
    except Exception as e:
        print(f"[Tag Error] {e}")

def create_demo_snippet(input_path, output_path, start_sec=35, duration_sec=40):
    sound = AudioSegment.from_file(input_path)
    start_ms = start_sec * 1000
    end_ms = (start_sec + duration_sec) * 1000

    if len(sound) <= end_ms:
        start_ms = 0
        end_ms = min(len(sound), duration_sec * 1000)

    demo = sound[start_ms:end_ms]
    demo = demo.fade_in(2000).fade_out(2500)
    demo.export(output_path, format="mp3", bitrate="192k")

@user_client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def source_detector(event):
    if event.audio:
        title = ""
        for attr in event.message.media.document.attributes:
            if isinstance(attr, DocumentAttributeAudio):
                title = attr.title or ""
                break

        track_id = f"{event.chat_id}_{event.id}"
        if track_id not in PROCESSED_TRACKS:
            PROCESSED_TRACKS.add(track_id)
            MUSIC_QUEUE.append(event.message)
            print(f"[Queue] New remix detected: {title or 'Unknown'}")

async def scheduler_poster():
    while True:
        try:
            if MUSIC_QUEUE:
                msg = MUSIC_QUEUE.pop(0)
                print(f"[Worker] Starting process for message: {msg.id}")

                raw_title = "ریمیکس جدید"
                duration = 0
                if msg.audio:
                    for attr in msg.audio.attributes:
                        if isinstance(attr, DocumentAttributeAudio):
                            if attr.title:
                                raw_title = attr.title
                            if attr.duration:
                                duration = attr.duration

                clean_title = re.sub(r'@[A-Za-z0-9_]+', '', raw_title).strip()
                display_channel = f"@{TARGET_CHANNEL.replace('@', '')}"

                temp_full = f"full_{msg.id}.mp3"
                temp_demo = f"demo_{msg.id}.mp3"

                await user_client.download_media(msg, file=temp_full)
                update_metadata_and_cover(temp_full, clean_title, display_channel, COVER_PATH)
                create_demo_snippet(temp_full, temp_demo)

                caption_full = (
                    f"🎧 **{clean_title}**\n"
                    f"▫️ کیفیت اصلی ۳۲۰\n\n"
                    f"🆔 {display_channel}"
                )
                caption_demo = (
                    f"🔊 **پیش‌نمایش ریمیکس (Demo)**\n"
                    f"▫️ آهنگ کامل بلافاصله در پیام بعدی 👇\n\n"
                    f"🆔 {display_channel}"
                )

                await bot_client.send_file(
                    TARGET_CHANNEL,
                    temp_demo,
                    caption=caption_demo,
                    attributes=[DocumentAttributeAudio(duration=40, title=f"{clean_title} (Demo)", performer=display_channel)]
                )
                await asyncio.sleep(2)
                await bot_client.send_file(
                    TARGET_CHANNEL,
                    temp_full,
                    caption=caption_full,
                    attributes=[DocumentAttributeAudio(duration=duration, title=clean_title, performer=display_channel)]
                )

                if os.path.exists(temp_full):
                    os.remove(temp_full)
                if os.path.exists(temp_demo):
                    os.remove(temp_demo)

                print(f"[Worker] Track published successfully: {clean_title}")

        except Exception as e:
            print(f"[Worker Error] {e}")

        await asyncio.sleep(POST_INTERVAL)

async def main():
    await user_client.start()
    await bot_client.start(bot_token=BOT_TOKEN)
    print("Selfbot & Channel Bot are running successfully.")

    asyncio.create_task(scheduler_poster())
    
    await asyncio.gather(
        user_client.run_until_disconnected(),
        bot_client.run_until_disconnected()
    )

if __name__ == '__main__':
    asyncio.run(main())
