import os
import asyncio
import re
import io
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeAudio
from telethon.tl.functions.account import UpdateProfileRequest
from pydub import AudioSegment
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, COMM, APIC
from PIL import Image

# --- تنظیمات متغیرهای محیطی ---
API_ID = int(os.getenv('API_ID', '2040'))
API_HASH = os.getenv('API_HASH', 'b18441a1ff607e10a989891a5462e627')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
STRING_SESSION = os.getenv('STRING_SESSION', '')

TARGET_CHANNEL = os.getenv('TARGET_CHANNEL', '@xibopay')
POST_INTERVAL = int(os.getenv('POST_INTERVAL', '15'))  # زمان تست سریع
PROXY_CHANNEL = 'iRoProxy'

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

async def get_latest_proxy():
    """بررسی ۵ پست آخر کانال پروکسی با اولویت جدیدترین پست‌های منتشر شده"""
    try:
        pattern = r'(https?://t\.me/proxy\?[^\s]+|tg://proxy\?[^\s]+)'
        async for msg in user_client.iter_messages(PROXY_CHANNEL, limit=5):
            # بررسی متن پیام
            if msg.text:
                found = re.findall(pattern, msg.text)
                if found:
                    return found[0]

            # بررسی دکمه‌های پیام (Inline Buttons)
            if msg.buttons:
                for row in msg.buttons:
                    for btn in row:
                        if btn.url and ('proxy?' in btn.url):
                            return btn.url
    except Exception as e:
        print(f"[Proxy Fetch Error] {e}")

    return "https://t.me/iRoProxy"

def analyze_bpm_and_vibe(sound_segment, track_title=""):
    title_lower = (track_title or "").lower()

    dark_keywords = ['dep', 'dark', 'sad', 'ghamgin', 'gham', 'tanha', 'del', 'ghose', 'tanhae', 'بغض', 'غم', 'دارک', 'گریه', 'دپ', 'تنهایی', 'خاطره', 'اشک', 'دلشکسته', 'دلگیر', 'مرگ', 'شب']
    romantic_keywords = ['love', 'romantic', 'delbar', 'eshgh', 'yar', 'baroon', 'عشق', 'عاشقانه', 'دلبر', 'بارون', 'آروم', 'چشمات', 'آرامش', 'یار', 'جانم', 'من و تو']
    party_keywords = ['party', 'dance', 'shad', 'raghs', 'bomb', 'gheri', 'wedding', 'قر', 'شاد', 'پارتی', 'عروسی', 'انرژی', 'ترکوندن', 'بندری', 'هللیوس']
    gang_keywords = ['bass boost', 'heavy bass', 'drill', 'gang', 'shooti', 'بیس سنگین', 'دریل', 'شوتی', 'بیس دار', 'گنگستر', 'سیستمی']

    if any(k in title_lower for k in dark_keywords):
        return 85, "🥀 فاز غمگین / دارک"
    if any(k in title_lower for k in romantic_keywords):
        return 98, "🍷 فاز رمانتیک"
    if any(k in title_lower for k in party_keywords):
        return 126, "💃 شاد و شنگول"
    if any(k in title_lower for k in gang_keywords):
        return 140, "🚀 فاز سنگین / بیس‌دار"

    try:
        sample_audio = sound_segment[40000:70000]
        if len(sample_audio) < 10000:
            sample_audio = sound_segment[:25000]

        bass_audio = sample_audio.set_channels(1).low_pass_filter(160)
        samples = bass_audio.get_array_of_samples()

        if not samples:
            return 115, "🏎️ فاز دور دور"

        total_energy = sum(s * s for s in samples[::50])
        rms = (total_energy / max(len(samples[::50]), 1)) ** 0.5

        peak_threshold = max(abs(s) for s in samples[::50]) * 0.72
        kick_count = 0
        cooldown = 0
        min_cooldown = int(bass_audio.frame_rate * 0.35)

        for s in samples:
            if cooldown > 0:
                cooldown -= 1
                continue
            if abs(s) > peak_threshold:
                kick_count += 1
                cooldown = min_cooldown

        duration_sec = len(bass_audio) / 1000.0
        calculated_tempo = int((kick_count / duration_sec) * 60)

        if calculated_tempo >= 128 and rms > 6500:
            vibe = "🚀 فاز سنگین / بیس‌دار"
        elif 118 <= calculated_tempo < 128:
            vibe = "🏎️ فاز دور دور"
        elif 108 <= calculated_tempo < 118:
            vibe = "💃 شاد و شنگول"
        elif 96 <= calculated_tempo < 108:
            vibe = "✨ فاز قیلی‌ویلیتور"
        elif 84 <= calculated_tempo < 96:
            vibe = "🍷 فاز رمانتیک"
        else:
            vibe = "🥀 فاز غمگین / دارک"

        return calculated_tempo, vibe

    except Exception as e:
        print(f"[Vibe Fallback] {e}")
        return 112, "🏎️ فاز دور دور"

def update_metadata_and_cover(file_path, title, artist, cover_file):
    try:
        try:
            audio = MP3(file_path, ID3=ID3)
        except Exception:
            audio = MP3(file_path)
            audio.add_tags()

        if audio.tags is None:
            audio.add_tags()

        audio.tags.delall('APIC')

        clean_channel = TARGET_CHANNEL.replace('@', '').replace('https://t.me/', '')
        audio.tags.add(TIT2(encoding=3, text=title))
        audio.tags.add(TPE1(encoding=3, text=artist))
        audio.tags.add(COMM(encoding=3, lang='eng', desc='', text=f'https://t.me/{clean_channel}'))

        if os.path.exists(cover_file):
            with Image.open(cover_file) as img:
                img = img.convert('RGB')
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG', quality=95)
                img_data = img_byte_arr.getvalue()

            audio.tags.add(APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,
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

        await asyncio.sleep(60)

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

                # دریافت جدیدترین پروکسی فعال از ۵ پست اخیر
                proxy_link = await get_latest_proxy()

                m, s = divmod(start_sec, 60)
                timestamp_str = f"{m:02d}:{s:02d}"

                caption_demo = (
                    f"<b>name: {track_name}</b>\n"
                    f"<b>Demo⚠️⏯️</b>\n\n"
                    f"<blockquote><b>🆔 @{clean_target}</b></blockquote>\n\n"
                    f"<b>🛑O.file👇</b>"
                )

                # کلمه proxy زیر full music به صورت بولد و لینک‌دار بدون کیوت
                caption_full = (
                    f"<b>name: {track_name}</b>\n"
                    f"<b>full music ✅️⏯️</b>\n"
                    f"<a href=\"{proxy_link}\"><b>proxy</b></a>\n\n"
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

                if os.path.exists(temp_full):
                    os.remove(temp_full)
                if os.path.exists(temp_demo):
                    os.remove(temp_demo)

                print(f"[Publisher] Posted successfully: {track_name}")

        except Exception as e:
            print(f"[Publisher Error] {e}")

        await asyncio.sleep(POST_INTERVAL)

async def main():
    print("[Init] Connecting user client...")
    await user_client.connect()

    if not await user_client.is_user_authorized():
        print("[Auth Error] STRING_SESSION نامعتبر یا منقضی شده است!")
        return

    print("User Client is online and connected!")

    try:
        await user_client(UpdateProfileRequest(about="ID/@xibopay"))
        print("[Profile] Bio set to ID/@xibopay successfully.")
    except Exception as e:
        print(f"[Profile Bio Error] {e}")

    print("[Init] Starting bot client...")
    await bot_client.start(bot_token=BOT_TOKEN)
    print("Channel Bot is online and running...")

    asyncio.create_task(scan_sources_cycle())
    asyncio.create_task(publisher_worker())

    await bot_client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
