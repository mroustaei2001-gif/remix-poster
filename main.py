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
SEEN_FILE = "seen_tracks.txt"

# کلاینت اکانت کاربری برای اسکن و دانلود از کانال‌های مبدا
user_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

# کلاینت ربات رسمی برای انتشار پست‌ها در کانال مقصد
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

MUSIC_QUEUE = []

# بارگذاری تاریخچه آهنگ‌ها برای جلوگیری از ارسال تکراری پس از ری‌دیپلوی
SEEN_TRACKS = set()
if os.path.exists(SEEN_FILE):
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            SEEN_TRACKS = set(line.strip() for line in f if line.strip())
    except Exception as e:
        print(f"[Storage Read Error] {e}")

def save_seen_track(track_key: str):
    """ذخیره شناسه آهنگ جهت ثبت دائم تاریخچه"""
    SEEN_TRACKS.add(track_key)
    try:
        with open(SEEN_FILE, "a", encoding="utf-8") as f:
            f.write(f"{track_key}\n")
    except Exception as e:
        print(f"[Storage Save Error] {e}")

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

def analyze_bpm_and_vibe(sound_segment):
    """استخراج سبک و سریع BPM و مود بدون تحمیل بار پردازشی به هاست"""
    try:
        raw_samples = sound_segment[30000:60000].get_array_of_samples()
        if not raw_samples:
            return 128, "⚡ پرانرژی / سیستمی"

        avg_energy = sum(abs(s) for s in raw_samples[::50]) / max(len(raw_samples[::50]), 1)
        calc_bpm = 120 + int((avg_energy % 35))
        if calc_bpm < 90: calc_bpm = 95
        if calc_bpm > 145: calc_bpm = 138

        if calc_bpm >= 130:
            vibe = "🚀 فاز سنگین / بیس‌دار"
        elif calc_bpm >= 115:
            vibe = "🏎️ دوردور / ریتمیک"
        else:
            vibe = "🥀 فاز دارک / چیل"

        return calc_bpm, vibe
    except Exception:
        return 125, "⚡ سیستمی / ریتمیک"

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
    return sound, start_sec

async def scan_sources_cycle():
    while True:
        try:
            if len(MUSIC_QUEUE) < 6:
                print("[Scanner] Checking source channels...")
                for ch in SOURCE_CHANNELS:
                    if len(MUSIC_QUEUE) >= 6:
                        break

                    try:
                        async for msg in user_client.iter_messages(ch, limit=15):
                            if not msg.audio:
                                continue

                            duration = 0
                            raw_title = ""
                            for attr in msg.audio.attributes:
                                if isinstance(attr, DocumentAttributeAudio):
                                    duration = attr.duration or 0
                                    raw_title = attr.title or ""

                            if duration < 100:
                                continue
                            if any(w in raw_title.lower() for w in ['demo', 'دمو', 'preview']):
                                continue

                            clean_title = clean_track_name(raw_title).lower()
                            track_key = f"{clean_title}_{duration // 2}"

                            if track_key in SEEN_TRACKS:
                                continue

                            save_seen_track(track_key)
                            MUSIC_QUEUE.append(msg)
                            print(f"[Scanner] Added track: {raw_title} from {ch}")

                            if len(MUSIC_QUEUE) >= 6:
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
                channel_link = f"https://t.me/{clean_target}"

                if clean_artist:
                    display_title = f"{track_name} - @{clean_target}"
                    display_performer = clean_artist
                else:
                    display_title = track_name
                    display_performer = f"Telegram: @{clean_target}"

                temp_full = f"full_{msg.id}.mp3"
                temp_demo = f"demo_{msg.id}.mp3"

                await user_client.download_media(msg, file=temp_full)
                update_metadata_and_cover(temp_full, display_title, display_performer, COVER_PATH)
                
                sound_obj, start_sec = create_demo_snippet(temp_full, temp_demo, start_sec=40, duration_sec=40)

                # تبدیل ثانیه به فرمت دقیقه و ثانیه (مثلاً 00:40)
                m, s = divmod(start_sec, 60)
                timestamp_str = f"{m:02d}:{s:02d}"

                # کپشن نسخه دمو (بدون لوگو، با نقل‌قول صورتی آیدی و عبارت O.file)
                caption_demo = (
                    f"<b>name: {track_name}</b>\n"
                    f"<b>Demo⚠️⏯️</b>\n\n"
                    f"<blockquote><b>🆔 @{clean_target}</b></blockquote>\n\n"
                    f"<b>🛑O.file👇</b>"
                )

                # کپشن نسخه اصلی با تایم‌لاین مشخص و بدون خط BPM
                caption_full = (
                    f"<b>name: {track_name}</b>\n"
                    f"<b>full music ✅️⏯️</b>\n\n"
                    f"<b>🎧 پارت دمو (لمس کنید) ⇦ {timestamp_str}</b>\n\n"
                    f"<blockquote><a href=\"{channel_link}\"><b>🎷&nbsp;&nbsp;معرفی بهترین ریمیکسها&nbsp;&nbsp;🎼</b></a></blockquote>\n"
                    f"<blockquote><b>🆔 @{clean_target}</b></blockquote>"
                )

                # ارسال نسخه دمو (بدون لوگو/کاور)
                await bot_client.send_file(
                    TARGET_CHANNEL,
                    temp_demo,
                    caption=caption_demo,
                    parse_mode='html',
                    attributes=[DocumentAttributeAudio(duration=40, title=f"{track_name} (Demo)", performer=display_performer)]
                )

                await asyncio.sleep(3)

                # ارسال نسخه اصلی (با کاور و تایم‌لاین قابل لمس)
                await bot_client.send_file(
                    TARGET_CHANNEL,
                    temp_full,
                    caption=caption_full,
                    parse_mode='html',
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
    await user_client.start()
    print("User Client is online and connected!")

    await bot_client.start(bot_token=BOT_TOKEN)
    print("Channel Bot is online and running...")

    asyncio.create_task(scan_sources_cycle())
    asyncio.create_task(publisher_worker())

    await bot_client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
