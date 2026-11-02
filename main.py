import os
import asyncio
import re
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeAudio
from pydub import AudioSegment
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, COMM, APIC

# دریافت متغیرها از ریل‌وی
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
STRING_SESSION = os.getenv('STRING_SESSION', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

TARGET_CHANNEL = os.getenv('TARGET_CHANNEL', 'xibopay')
POST_INTERVAL = int(os.getenv('POST_INTERVAL', '10800'))  # هر ۳ ساعت (۱۰۸۰۰ ثانیه)

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

user_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
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
                        async for msg in user_client.iter_messages(ch, limit=10):
                            if not msg.audio:
                                continue

                            duration = 0
                            raw_title = ""
                            for attr in msg.audio.attributes:
                                if isinstance(attr, DocumentAttributeAudio):
                                    duration = attr.duration or 0
                                    raw_title = attr.title or ""

                            # نادیده گرفتن دموهای کانال منبع
                            if duration < 100:
                                continue
                            if any(w in raw_title.lower() for w in ['demo', 'دمو', 'preview']):
                                continue

                            clean_title = clean_track_name(raw_title).lower()
                            # کلید ضد تکرار: نام + طول تقریبی با تلورانس ۲ ثانیه
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

        # اسکن مجدد هر ۲۰ دقیقه برای موزیک‌های جدید
        await asyncio.sleep(1200)

async def publisher_worker():
    while True:
        try:
            if MUSIC_QUEUE:
                msg = MUSIC_QUEUE.pop(0)
                print(f"[Publisher] Processing track ID {msg.id}...")

                raw_title = "New Remix"
                duration = 0
                for attr in msg.audio.attributes:
                    if isinstance(attr, DocumentAttributeAudio):
                        if attr.title:
                            raw_title = attr.title
                        if attr.duration:
                            duration = attr.duration

                track_name = clean_track_name(raw_title)
                clean_target = TARGET_CHANNEL.replace('@', '').replace('https://t.me/', '')
                channel_link = f"https://t.me/{clean_target}"

                temp_full = f"full_{msg.id}.mp3"
                temp_demo = f"demo_{msg.id}.mp3"

                await user_client.download_media(msg, file=temp_full)
                update_metadata_and_cover(temp_full, track_name, f"@{clean_target}", COVER_PATH)
                create_demo_snippet(temp_full, temp_demo)

                # متون کپشن درخواستی
                caption_demo = (
                    f"{track_name}\n"
                    f"play by demo⏯️\n"
                    f"🆔️ایدی چنل تست \n"
                    f"({channel_link})\n"
                    f"d.org.music👇"
                )

                caption_full = (
                    f"{track_name} \n"
                    f"org.music⏯️✅️\n"
                    f"🆔️ایدی چنل تست \n"
                    f"({channel_link})"
                )

                # ارسال نسخه دمو
                await bot_client.send_file(
                    TARGET_CHANNEL,
                    temp_demo,
                    caption=caption_demo,
                    attributes=[DocumentAttributeAudio(duration=40, title=f"{track_name} (Demo)", performer=f"@{clean_target}")]
                )

                await asyncio.sleep(3)

                # ارسال موزیک اصلی
                await bot_client.send_file(
                    TARGET_CHANNEL,
                    temp_full,
                    caption=caption_full,
                    attributes=[DocumentAttributeAudio(duration=duration, title=track_name, performer=f"@{clean_target}")]
                )

                if os.path.exists(temp_full): os.remove(temp_full)
                if os.path.exists(temp_demo): os.remove(temp_demo)

                print(f"[Publisher] Posted successfully: {track_name}")

        except Exception as e:
            print(f"[Publisher Error] {e}")

        await asyncio.sleep(POST_INTERVAL)

async def main():
    await user_client.start()
    await bot_client.start(bot_token=BOT_TOKEN)
    print("Selfbot & Channel Bot are running.")

    asyncio.create_task(scan_sources_cycle())
    asyncio.create_task(publisher_worker())

    await asyncio.gather(
        user_client.run_until_disconnected(),
        bot_client.run_until_disconnected()
    )

if __name__ == '__main__':
    asyncio.run(main())
