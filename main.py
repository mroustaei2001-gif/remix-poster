import os
import asyncio
import re
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeAudio
from pydub import AudioSegment
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, COMM, APIC

# --- متغیرهای محیطی در Railway ---
API_ID = int(os.getenv('API_ID', '2040'))
API_HASH = os.getenv('API_HASH', 'b18441a1ff607e10a989891a5462e627')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
STRING_SESSION = os.getenv('STRING_SESSION', '')

TARGET_CHANNEL = os.getenv('TARGET_CHANNEL', '@xibopay')
POST_INTERVAL = int(os.getenv('POST_INTERVAL', '10800'))  # پیش‌فرض ۳ ساعت

SOURCE_CHANNELS = [
    'RapRemixxx',
    'melody9',
    'resanejavon',
    'RapExclusivee',
    'RiMixaM',
    'ReMiXeQofli',
    'nayabrapi'
]

COVER_PATH = "cover.png"

# کلاینت اکانت کاربری برای اسکن و دانلود از کانال‌های مبدا
user_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

# کلاینت بات رسمی برای آپلود و پست در کانال مقصد
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

MUSIC_QUEUE = []
SEEN_TRACKS = set()

def clean_track_name(title):
    if not title:
        return "Remix"
    title = re.sub(r'@[A-Za-z0-9_]+', '', title)
    title = re.sub(r'https?://\S+', '', title)
    title = re.sub(r'[\(\[\{].*?[\)\]\}]', '', title)
    return title.strip() or "Remix"

def clean_artist_name(performer):
    if not performer:
        return ""
    performer = re.sub(r'@[A-Za-z0-9_]+', '', performer)
    performer = re.sub(r'https?://\S+', '', performer)
    return performer.strip()

def update_metadata_and_cover(file_path, title, artist, cover_file):
    try:
        audio = MP3(file_path, ID3=ID3)
        try:
            audio.add_tags()
        except Exception:
            pass

        clean_channel = TARGET_CHANNEL.replace('@', '').replace('https://t.me/', '')
        audio.tags.add(TIT2(encoding=3, text=title))
        audio.tags.add(TPE1(encoding=3, text=artist))
        audio.tags.add(COMM(encoding=3, lang='eng', desc='', text=f'https://t.me/{clean_channel}'))

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

def create_demo_snippet(input_path, output_path, start_sec=40, duration_sec=40):
    sound = AudioSegment.from_file(input_path)
    start_ms = start_sec * 1000
    end_ms = (start_sec + duration_sec) * 1000

    if len(sound) <= end_ms:
        start_ms = 0
        end_ms = min(len(sound), duration_sec * 1000)

    demo = sound[start_ms:end_ms]
    demo = demo.fade_in(2000).fade_out(2500)
    demo.export(output_path, format="mp3", bitrate="192k")

async def scan_sources_cycle():
    while True:
        try:
            if len(MUSIC_QUEUE) < 4:
                print("[Scanner] Checking sources for new remixes...")
                collected_count = 0

                for ch in SOURCE_CHANNELS:
                    if len(MUSIC_QUEUE) >= 4 or collected_count >= 4:
                        break

                    try:
                        # اسکن باید با user_client انجام شود نه با bot_client
                        async for msg in user_client.iter_messages(ch, limit=10):
                            if not msg.audio:
                                continue

                            duration = 0
                            raw_title = ""
                            for attr in msg.audio.attributes:
                                if isinstance(attr, DocumentAttributeAudio):
                                    duration = attr.duration or 0
                                    raw_title = attr.title or ""

                            # فیلتر دموهای کانال منبع
                            if duration < 100:
                                continue
                            if any(w in raw_title.lower() for w in ['demo', 'دمو', 'preview']):
                                continue

                            clean_title = clean_track_name(raw_title).lower()
                            track_key = f"{clean_title}_{duration // 2}"

                            if track_key in SEEN_TRACKS:
                                continue

                            SEEN_TRACKS.add(track_key)
                            MUSIC_QUEUE.append(msg)
                            collected_count += 1
                            print(f"[Scanner] Added track: {raw_title} ({duration}s)")

                            if len(MUSIC_QUEUE) >= 4 or collected_count >= 4:
                                break
                    except Exception as ch_err:
                        print(f"[Scanner Channel Error] {ch}: {ch_err}")

        except Exception as e:
            print(f"[Scanner Main Error] {e}")

        await asyncio.sleep(1200)

async def publisher_worker():
    while True:
        try:
            if MUSIC_QUEUE:
                msg = MUSIC_QUEUE.pop(0)
                print(f"[Publisher] Processing track ID {msg.id}...")

                raw_title = "New Remix"
                raw_performer = ""
                duration = 0
                for attr in msg.audio.attributes:
                    if isinstance(attr, DocumentAttributeAudio):
                        if attr.title:
                            raw_title = attr.title
                        if attr.performer:
                            raw_performer = attr.performer
                        if attr.duration:
                            duration = attr.duration

                track_name = clean_track_name(raw_title)
                clean_artist = clean_artist_name(raw_performer)
                clean_target = TARGET_CHANNEL.replace('@', '').replace('https://t.me/', '')

                # تنظیم نام و خواننده در پلیر تلگرام
                if clean_artist:
                    display_title = f"{track_name} - @{clean_target}"
                    display_performer = clean_artist
                else:
                    display_title = track_name
                    display_performer = f"Telegram: @{clean_target}"

                temp_full = f"full_{msg.id}.mp3"
                temp_demo = f"demo_{msg.id}.mp3"

                # دانلود قطعه توسط کلاینت اکانت کاربری
                await user_client.download_media(msg, file=temp_full)
                update_metadata_and_cover(temp_full, display_title, display_performer, COVER_PATH)
                create_demo_snippet(temp_full, temp_demo)

                # متن کپشن دمو (بدون لوگو، با نقل‌قول مارک‌داون و بولد)
                caption_demo = (
                    f"name: {track_name}\n"
                    f"Demo⚠️⏯️\n"
                    f"> **🆔 @{clean_target}**\n"
                    f"org.m👇"
                )

                # متن کپشن نسخه اصلی (همراه با معرفی و آیدی داخل نقل‌قول و بولد)
                caption_full = (
                    f"name: {track_name}\n"
                    f"full music ✅️⏯️\n\n"
                    f"> **معرفی بهترین ریمیکسها 🎼🎷**\n"
                    f"> **🆔 @{clean_target}**"
                )

                # ارسال نسخه دمو (بدون thumb برای حذف لوگو)
                await bot_client.send_file(
                    TARGET_CHANNEL,
                    temp_demo,
                    caption=caption_demo,
                    parse_mode='md',
                    attributes=[DocumentAttributeAudio(duration=40, title=f"{track_name} (Demo)", performer=display_performer)]
                )

                await asyncio.sleep(3)

                # ارسال نسخه اصلی (با کاور و اطلاعات کامل)
                await bot_client.send_file(
                    TARGET_CHANNEL,
                    temp_full,
                    caption=caption_full,
                    parse_mode='md',
                    thumb=COVER_PATH if os.path.exists(COVER_PATH) else None,
                    attributes=[DocumentAttributeAudio(duration=duration, title=display_title, performer=display_performer)]
                )

                if os.path.exists(temp_full): os.remove(temp_full)
                if os.path.exists(temp_demo): os.remove(temp_demo)

                print(f"[Publisher] Posted successfully: {track_name}")

        except Exception as e:
            print(f"[Publisher Error] {e}")

        await asyncio.sleep(POST_INTERVAL)

async def main():
    # روشن کردن کلاینت اکانت برای خواندن کانال‌ها
    await user_client.start()
    print("User Client is online and connected!")

    # روشن کردن کلاینت ربات رسمی برای انتشار پست‌ها
    await bot_client.start(bot_token=BOT_TOKEN)
    print("Channel Bot is online and running...")

    asyncio.create_task(scan_sources_cycle())
    asyncio.create_task(publisher_worker())

    await bot_client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
