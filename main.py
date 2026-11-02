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

user_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

MUSIC_QUEUE = []

SEEN_TRACKS = set()
if os.path.exists(SEEN_FILE):
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            SEEN_TRACKS = set(line.strip() for line in f if line.strip())
    except Exception as e:
        print(f"[Storage Read Error] {e}")

def save_seen_track(track_key: str):
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

def analyze_bpm_and_vibe(sound_segment, track_title=""):
    title_lower = (track_title or "").lower()

    # ۱. اولویت اول: فیلتر کلمات کلیدی در نام موزیک
    dark_keywords = ['dep', 'dark', 'sad', 'ghamgin', 'gham', 'tanha', 'del', 'ghose', 'tanhae', 'بغض', 'غم', 'دارک', 'گریه', 'دپ', 'تنهایی', 'خاطره', 'اشک', 'دلشکسته', 'دلگیر', 'مرگ']
    romantic_keywords = ['love', 'romantic', 'delbar', 'eshgh', 'yar', 'عشق', 'عاشقانه', 'دلبر', 'بارون', 'آروم', 'چشمات', 'آرامش', 'یار']
    party_keywords = ['party', 'dance', 'shad', 'raghs', 'bomb', 'قر', 'شاد', 'پارتی', 'عروسی', 'انرژی', 'ترکوندن']
    gang_keywords = ['bass', 'trap', 'gang', 'heavy', 'drill', 'بیس', 'گنگ', 'شوتی', 'دریل', 'سنگین']

    if any(k in title_lower for k in dark_keywords):
        return 85, "🥀 فاز غمگین / دارک"
    if any(k in title_lower for k in romantic_keywords):
        return 98, "🍷 فاز رمانتیک"
    if any(k in title_lower for k in party_keywords):
        return 126, "💃 شاد و شنگول"
    if any(k in title_lower for k in gang_keywords):
        return 138, "🚀 فاز سنگین / بیس‌دار"

    # ۲. تحلیل ضربان صوتی (پیدا کردن پیک‌های بیس در بازه اوج آهنگ)
    try:
        # نمونه‌گیری از ثانیه ۴۰ تا ۷۰ (پارت ورس/اوج)
        sample_audio = sound_segment[40000:70000]
        if len(sample_audio) < 10000:
            sample_audio = sound_segment[:30000]

        # تبدیل به مونو و گرفتن داده‌های نمونه
        samples = sample_audio.set_channels(1).get_array_of_samples()
        if not samples:
            return 120, "🏎️ فاز دور دور"

        # شناسایی ضربان‌ها (پیک‌های بلند با فاصله زمانی مشخص)
        peak_count = 0
        threshold = max(abs(s) for s in samples[::100]) * 0.65
        cooldown = 0
        min_cooldown = int(sample_audio.frame_rate * 0.28) # حداقل فاصله بین دو ضرب بیس

        for s in samples:
            if cooldown > 0:
                cooldown -= 1
                continue
            if abs(s) > threshold:
                peak_count += 1
                cooldown = min_cooldown

        # تبدیل تعداد ضرب‌ها در ۳۰ ثانیه به تمپو در دقیقه (BPM)
        duration_sec = len(sample_audio) / 1000.0
        bpm = int((peak_count / duration_sec) * 60)

        # دسته‌بندی واقع‌گرایانه
        if bpm >= 135:
            vibe = "🚀 فاز سنگین / بیس‌دار"
        elif 122 <= bpm < 135:
            vibe = "🏎️ فاز دور دور"
        elif 112 <= bpm < 122:
            vibe = "💃 شاد و شنگول"
        elif 100 <= bpm < 112:
            vibe = "✨ فاز قیلی‌ویلیتور"
        elif 88 <= bpm < 100:
            vibe = "🍷 فاز رمانتیک"
        else:
            vibe = "🥀 فاز غمگین / دارک"

        return bpm, vibe

    except Exception:
        return 110, "🏎️ فاز دور دور"


def update_metadata_and_cover(file_path, title, artist, cover_file):
    try:
        try:
            audio = MP3(file_path, ID3=ID3)
        except Exception:
            audio = MP3(file_path)
            audio.add_tags()

        if audio.tags is None:
            audio.add_tags()

        # حذف تمامی تگ‌های کاور قبلی که از قبل روی فایل بوده است
        audio.tags.delall('APIC')

        clean_channel = TARGET_CHANNEL.replace('@', '').replace('https://t.me/', '')
        audio.tags.add(TIT2(encoding=3, text=title))
        audio.tags.add(TPE1(encoding=3, text=artist))
        audio.tags.add(COMM(encoding=3, lang='eng', desc='', text=f'https://t.me/{clean_channel}'))

        if os.path.exists(cover_file):
            # تبدیل کاور به فرمت استاندارد JPEG یا PNG برای خوانده‌شدن در پلیر
            from PIL import Image
            import io
            
            with Image.open(cover_file) as img:
                img = img.convert('RGB')
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG', quality=95)
                img_data = img_byte_arr.getvalue()

            audio.tags.add(APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,  # cover front
                desc='Cover',
                data=img_data
            ))

        audio.save(v2_version=3)
    except Exception as e:
        print(f"[Tag Error] {e}")


def create_demo_snippet(input_path, output_path, start_sec=40, duration_sec=40):
    sound = AudioSegment.from_file(input_path)
    start_ms = start_sec * 1000
    end_ms = (start_sec + duration_sec) * 1000

    if len(sound) <= end_ms:
        start_sec = 0
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
                _, vibe = analyze_bpm_and_vibe(sound_obj, track_title=track_name)

                m, s = divmod(start_sec, 60)
                timestamp_str = f"{m:02d}:{s:02d}"

                caption_demo = (
                    f"<b>name: {track_name}</b>\n"
                    f"<b>Demo⚠️⏯️</b>\n\n"
                    f"<blockquote><b>🆔 @{clean_target}</b></blockquote>\n\n"
                    f"<b>🛑O.file👇</b>"
                )

                caption_full = (
                    f"<b>name: {track_name}</b>\n"
                    f"<b>full music ✅️⏯️</b>\n\n"
                    f"<b>🎧 پارت دمو (لمس کنید) ⇦ {timestamp_str}</b>\n"
                    f"<b>{vibe}</b>\n\n"
                    f"<blockquote><a href=\"{channel_link}\"><b>🎷&nbsp;&nbsp;معرفی بهترین ریمیکسها&nbsp;&nbsp;🎼</b></a></blockquote>\n"
                    f"<blockquote><b>🆔 @{clean_target}</b></blockquote>"
                )

                await bot_client.send_file(
                    TARGET_CHANNEL,
                    temp_demo,
                    caption=caption_demo,
                    parse_mode='html',
                    attributes=[DocumentAttributeAudio(duration=40, title=f"{track_name} (Demo)", performer=display_performer)]
                )

                await asyncio.sleep(3)

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
    # اتصال قطعی کلاینت کاربر با سشن استرینگ
    print("[Init] Connecting user client...")
    await user_client.connect()
    
    if not await user_client.is_user_authorized():
        print("[Auth Error] STRING_SESSION نامعتبر یا منقضی شده است!")
        return

    print("User Client is online and connected!")

    # اتصال ربات رسمی
    print("[Init] Starting bot client...")
    await bot_client.start(bot_token=BOT_TOKEN)
    print("Channel Bot is online and running...")

    # شروع تسک‌ها پس از اطمینان ۱۰۰٪ از اتصال هر دو کلاینت
    asyncio.create_task(scan_sources_cycle())
    asyncio.create_task(publisher_worker())

    await bot_client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
