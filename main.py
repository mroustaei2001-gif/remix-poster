import os
import sys
import asyncio
import re
import io
import random
import subprocess
from datetime import datetime, timezone, timedelta
from aiohttp import web
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeAudio, InputMediaUploadedPhoto
from telethon.tl.functions.messages import SendMediaRequest
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, COMM, APIC
from PIL import Image

IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

def log(msg):
    now_str = datetime.now(IRAN_TZ).strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now_str}] {msg}", flush=True)

log("Starting remix-poster production script...")

API_ID = int(os.getenv('API_ID', '2040'))
API_HASH = os.getenv('API_HASH', 'b18441a1ff607e10a989891a5462e627')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
STRING_SESSION = os.getenv('STRING_SESSION', '')

TARGET_CHANNEL = os.getenv('TARGET_CHANNEL', '@remixiyu')
PROXY_CHANNEL = 'iRoProxy'

SCHEDULE_HOURS = [2, 10, 14, 18, 22]

SOURCE_MUSIC_CHANNELS = [
    'RapRemixxx',
    'melody9',
    'resanejavon',
    'RapExclusivee',
    'RiMixaM',
    'ReMiXeQofli',
    'nayabrapi',
    'RAPFA_EDIT_REMIX',
    'Musicaeel',
    'PLAYVIBES'
]
FOREIGN_MUSIC_CHANNEL = 'DEEPHOUSEMUZIX'

SOURCE_PHOTO_CHANNELS = [
    'ahnGamw',
    'Maisam_saeedii',
    'RiMixaM',
    'PLAYVIBES'
]

COVER_PATH = "cover.png"
SEEN_FILE = "seen_tracks.txt"
SEEN_PHOTOS_FILE = "seen_photos.txt"

user_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

MUSIC_QUEUE = []
PHOTO_QUEUE = []
SEEN_TRACKS = set()
SEEN_PHOTOS = set()

INCLUDE_PHOTO_CYCLE = True

if os.path.exists(SEEN_FILE):
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            SEEN_TRACKS = set(line.strip() for line in f if line.strip())
        log(f"Loaded {len(SEEN_TRACKS)} tracks from history.")
    except Exception as e:
        log(f"Storage Music Error: {e}")

if os.path.exists(SEEN_PHOTOS_FILE):
    try:
        with open(SEEN_PHOTOS_FILE, "r", encoding="utf-8") as f:
            SEEN_PHOTOS = set(line.strip() for line in f if line.strip())
        log(f"Loaded {len(SEEN_PHOTOS)} photos from history.")
    except Exception as e:
        log(f"Storage Photo Error: {e}")

def save_seen_track(track_key: str):
    SEEN_TRACKS.add(track_key)
    try:
        with open(SEEN_FILE, "a", encoding="utf-8") as f:
            f.write(f"{track_key}\n")
    except Exception as e:
        log(f"Save Music Key Error: {e}")

def save_seen_photo(photo_key: str):
    SEEN_PHOTOS.add(photo_key)
    try:
        with open(SEEN_PHOTOS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{photo_key}\n")
    except Exception as e:
        log(f"Save Photo Key Error: {e}")

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

async def ensure_connection():
    if not user_client.is_connected():
        try:
            await user_client.connect()
        except Exception as e:
            log(f"Reconnect Error: {e}")

async def get_latest_proxy():
    try:
        await ensure_connection()
        async for msg in user_client.iter_messages(PROXY_CHANNEL, limit=5):
            if msg.buttons:
                for row in msg.buttons:
                    for btn in row:
                        if btn.url and ('proxy?' in btn.url):
                            link = btn.url
                            if link.startswith('https://t.me/proxy?'):
                                link = link.replace('https://t.me/proxy?', 'tg://proxy?')
                            return link

            if msg.entities:
                for ent, text in msg.get_entities_text():
                    if hasattr(ent, 'url') and ent.url and ('proxy?' in ent.url):
                        link = ent.url
                        if link.startswith('https://t.me/proxy?'):
                            link = link.replace('https://t.me/proxy?', 'tg://proxy?')
                        return link

            if msg.text:
                found = re.findall(r'(?:https?://t\.me/proxy\?|tg://proxy\?)[^\s<>"\'`]+', msg.text)
                if found:
                    link = found[0]
                    if link.startswith('https://t.me/proxy?'):
                        link = link.replace('https://t.me/proxy?', 'tg://proxy?')
                    return link
    except Exception as e:
        log(f"Proxy Fetch Error: {e}")

    return "https://t.me/iRoProxy"

def get_track_vibe(track_title="", is_foreign=False):
    if is_foreign:
        return "🌍 موزیک / خارجی"

    title_lower = (track_title or "").lower()

    dark_keywords = ['dep', 'dark', 'sad', 'ghamgin', 'gham', 'tanha', 'del', 'ghose', 'tanhae', 'بغض', 'غم', 'دارک', 'گریه', 'دپ', 'تنهایی', 'خاطره', 'اشک', 'دلشکسته', 'دلگیر', 'مرگ', 'شب']
    romantic_keywords = ['love', 'romantic', 'delbar', 'eshgh', 'yar', 'baroon', 'عشق', 'عاشقانه', 'دلبر', 'بارون', 'آروم', 'چشمات', 'آرامش', 'یار', 'جانم', 'من و تو']
    party_keywords = ['party', 'dance', 'shad', 'raghs', 'bomb', 'gheri', 'wedding', 'قر', 'شاد', 'پارتی', 'عروسی', 'انرژی', 'ترکوندن', 'بندری', 'هللیوس']
    gang_keywords = ['bass boost', 'heavy bass', 'drill', 'gang', 'shooti', 'بیس سنگین', 'دریل', 'شوتی', 'بیس دار', 'گنگستر', 'سیستمی']

    if any(k in title_lower for k in dark_keywords):
        return "🥀 فاز غمگین / دارک"
    if any(k in title_lower for k in romantic_keywords):
        return "🍷 فاز رمانتیک"
    if any(k in title_lower for k in party_keywords):
        return "💃 شاد و شنگول"
    if any(k in title_lower for k in gang_keywords):
        return "🚀 فاز سنگین / بیس‌دار"

    vibes = ["🏎️ فاز دور دور", "✨ فاز قیلی‌ویلیتور", "🚀 فاز سنگین / بیس‌دار", "🍷 فاز رمانتیک"]
    return random.choice(vibes)

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
        log(f"Tag Error: {e}")

def create_demo_voice_ffmpeg(input_path, output_path, start_sec=40, duration_sec=40):
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_sec),
        "-t", str(duration_sec),
        "-i", input_path,
        "-vn",
        "-c:a", "libopus",
        "-b:a", "48k",
        "-ar", "48000",
        "-ac", "1",
        "-application", "voip",
        "-af", "afade=t=in:ss=0:d=1,afade=t=out:st=38:d=2",
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return start_sec

async def scan_photos_cycle():
    while True:
        try:
            await ensure_connection()
            if len(PHOTO_QUEUE) < 6:
                sources = list(SOURCE_PHOTO_CHANNELS)
                random.shuffle(sources)

                for ch in sources:
                    if len(PHOTO_QUEUE) >= 6:
                        break
                    try:
                        count = 0
                        async for msg in user_client.iter_messages(ch, limit=300):
                            count += 1
                            if count % 30 == 0:
                                await asyncio.sleep(0.05)

                            is_valid_image = False
                            if msg.photo:
                                is_valid_image = True
                            elif msg.media and hasattr(msg.media, 'photo') and msg.media.photo:
                                is_valid_image = True

                            if not is_valid_image:
                                continue

                            caption = (msg.text or "").strip()

                            check_text = caption
                            if ch.lower() == 'playvibes':
                                check_text = re.sub(r'https?://(?:t\.me|telegram\.me)/(?:c/)?PLAYVIBES(?:/\d+)?', '', check_text, flags=re.IGNORECASE)
                                check_text = re.sub(r't\.me/PLAYVIBES(?:/\d+)?', '', check_text, flags=re.IGNORECASE)
                                check_text = re.sub(r'@PLAYVIBES', '', check_text, flags=re.IGNORECASE)

                            if re.search(r'(https?://|t\.me/|joinchat)', check_text, re.IGNORECASE):
                                continue

                            photo_key = f"photo_{msg.chat_id}_{msg.id}"
                            if photo_key in SEEN_PHOTOS:
                                continue

                            save_seen_photo(photo_key)
                            PHOTO_QUEUE.append(msg)
                            log(f"Photo Queued from {ch} (Total: {len(PHOTO_QUEUE)})")

                            if len(PHOTO_QUEUE) >= 6:
                                break
                    except Exception as err:
                        log(f"Photo Channel Error on {ch}: {err}")
        except Exception as e:
            log(f"Photo Cycle Error: {e}")

        await asyncio.sleep(60)

async def scan_music_cycle():
    while True:
        try:
            await ensure_connection()
            if len(MUSIC_QUEUE) < 8:
                all_channels = list(SOURCE_MUSIC_CHANNELS)
                if FOREIGN_MUSIC_CHANNEL not in all_channels:
                    all_channels.append(FOREIGN_MUSIC_CHANNEL)

                collected_candidates = []

                for ch in all_channels:
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

                            if duration < 100 or duration > 600:
                                continue

                            if any(w in raw_title.lower() for w in ['demo', 'دمو', 'preview']):
                                continue

                            clean_title = clean_track_name(raw_title).lower()
                            track_key = f"{clean_title}_{duration}"

                            if track_key in SEEN_TRACKS:
                                continue

                            is_foreign = (ch == FOREIGN_MUSIC_CHANNEL)
                            collected_candidates.append({
                                'msg': msg,
                                'is_foreign': is_foreign,
                                'date': msg.date,
                                'key': track_key,
                                'title': raw_title,
                                'duration': duration,
                                'channel': ch
                            })
                    except Exception as ch_err:
                        log(f"Music Scan Channel Error on {ch}: {ch_err}")

                collected_candidates.sort(key=lambda x: x['date'], reverse=True)

                for item in collected_candidates:
                    if len(MUSIC_QUEUE) >= 10:
                        break
                    save_seen_track(item['key'])
                    MUSIC_QUEUE.append((item['msg'], item['is_foreign']))
                    log(f"Music Queued (Newest): {item['title']} ({item['duration']}s) from {item['channel']} (Total: {len(MUSIC_QUEUE)})")

        except Exception as e:
            log(f"Music Cycle Error: {e}")

        await asyncio.sleep(60)

async def publisher_worker():
    global INCLUDE_PHOTO_CYCLE
    last_processed_slot = None

    while True:
        try:
            now = datetime.now(IRAN_TZ)
            current_hour = now.hour
            current_minute = now.minute

            if current_hour in SCHEDULE_HOURS and current_minute == 0:
                slot_key = f"{now.strftime('%Y-%m-%d')}_{current_hour}"
                if last_processed_slot != slot_key:
                    log(f"--- Triggering broadcast for {current_hour:02d}:00 ---")
                    await ensure_connection()

                    retry_wait = 0
                    while (len(MUSIC_QUEUE) < 2 or (INCLUDE_PHOTO_CYCLE and len(PHOTO_QUEUE) < 1)) and retry_wait < 12:
                        await asyncio.sleep(10)
                        retry_wait += 1

                    if len(MUSIC_QUEUE) >= 2:
                        clean_target = TARGET_CHANNEL.replace('@', '').replace('https://t.me/', '')
                        channel_link = f"https://t.me/{clean_target}"

                        temp_photo = None
                        photo_caption = ""
                        if INCLUDE_PHOTO_CYCLE and len(PHOTO_QUEUE) >= 1:
                            photo_msg = PHOTO_QUEUE.pop(0)
                            temp_photo = f"photo_{photo_msg.id}.jpg"
                            await user_client.download_media(photo_msg, file=temp_photo)
                            photo_caption = f'<blockquote><a href="{channel_link}"><b>🆔 @{clean_target}</b></a></blockquote>'

                        prepared_tracks = []
                        for idx in range(2):
                            msg, is_foreign = MUSIC_QUEUE.pop(0)

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

                            if clean_artist:
                                display_title = f"{track_name} - @{clean_target}"
                                display_performer = clean_artist
                            else:
                                display_title = track_name
                                display_performer = f"Telegram: @{clean_target}"

                            temp_full = f"full_{msg.id}.mp3"
                            temp_demo = f"demo_{msg.id}.ogg"

                            await user_client.download_media(msg, file=temp_full)
                            update_metadata_and_cover(temp_full, display_title, display_performer, COVER_PATH)

                            start_sec = create_demo_voice_ffmpeg(temp_full, temp_demo, start_sec=40, duration_sec=40)
                            vibe = get_track_vibe(track_title=track_name, is_foreign=is_foreign)

                            proxy_link = await get_latest_proxy()
                            m, s = divmod(start_sec, 60)
                            timestamp_str = f"{m:02d}:{s:02d}"

                            caption_demo = (
                                f"<b>name: {track_name}</b>\n"
                                f"<b>Demo⚠️⏯️</b>\n\n"
                                f'<blockquote><a href="{channel_link}"><b>🆔 @{clean_target}</b></a></blockquote>\n\n'
                                f"<b>🛑O.file👇</b>"
                            )

                            caption_full = (
                                f"<b>name: {track_name}</b>\n"
                                f"<b>full music ✅️⏯️</b>\n"
                                f'<a href="{proxy_link}"><b>proxy</b></a>\n\n'
                                f"<b>🎧 پارت دمو (لمس کنید) ⇦ {timestamp_str}</b>\n"
                                f"<b>{vibe}</b>\n\n"
                                f'<blockquote><a href="{channel_link}"><b>🎷&nbsp;&nbsp;معرفی بهترین ریمیکسها&nbsp;&nbsp;🎼</b></a></blockquote>\n'
                                f"<blockquote><b>🆔 @{clean_target}</b></blockquote>"
                            )

                            prepared_tracks.append({
                                "temp_demo": temp_demo,
                                "caption_demo": caption_demo,
                                "temp_full": temp_full,
                                "caption_full": caption_full,
                                "duration": duration,
                                "display_title": display_title,
                                "display_performer": display_performer
                            })

                        log("Broadcasting package to production channel...")

                        if temp_photo and os.path.exists(temp_photo):
                            uploaded_photo = await bot_client.upload_file(temp_photo)
                            target_peer = await bot_client.get_input_entity(TARGET_CHANNEL)
                            caption_text, entities = await bot_client._parse_message_text(photo_caption, 'html')

                            await bot_client(SendMediaRequest(
                                peer=target_peer,
                                media=InputMediaUploadedPhoto(file=uploaded_photo, spoiler=True),
                                message=caption_text,
                                entities=entities,
                                silent=True
                            ))
                            os.remove(temp_photo)

                        for t in prepared_tracks:
                            await bot_client.send_file(
                                TARGET_CHANNEL,
                                t["temp_demo"],
                                caption=t["caption_demo"],
                                parse_mode='html',
                                voice_note=True,
                                silent=True
                            )

                            await bot_client.send_file(
                                TARGET_CHANNEL,
                                t["temp_full"],
                                caption=t["caption_full"],
                                parse_mode='html',
                                silent=True,
                                thumb=COVER_PATH if os.path.exists(COVER_PATH) else None,
                                attributes=[DocumentAttributeAudio(duration=t["duration"], title=t["display_title"], performer=t["display_performer"])]
                            )

                        for t in prepared_tracks:
                            if os.path.exists(t["temp_demo"]):
                                os.remove(t["temp_demo"])
                            if os.path.exists(t["temp_full"]):
                                os.remove(t["temp_full"])

                        INCLUDE_PHOTO_CYCLE = not INCLUDE_PHOTO_CYCLE
                        last_processed_slot = slot_key
                        log(f"Broadcast successful! Next slot photo status: {INCLUDE_PHOTO_CYCLE}")

        except Exception as e:
            log(f"Publisher Worker Error: {e}")

        await asyncio.sleep(40)

# وب‌سرور داخلی برای راضی نگه‌داشتن سیستم بازرسی پورت ریل‌وی
async def handle_ping(request):
    return web.Response(text="OK")

async def run_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/health', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    log(f"Keep-Alive Server listening on port {port}...")

async def main():
    # ۱. اول سرور شبکه بالا می‌آید تا ریل‌وی پورت را تایید کند
    await run_server()

    # ۲. سپس اتصال کلاینت‌ها و شروع چرخه‌ها
    log("Connecting user client...")
    await user_client.start()

    if not await user_client.is_user_authorized():
        log("Auth Error: STRING_SESSION is unauthorized!")
        return

    me = await user_client.get_me()
    log(f"User Client connected successfully as @{me.username or me.id}!")

    log("Connecting channel bot...")
    await bot_client.start(bot_token=BOT_TOKEN)
    bot_info = await bot_client.get_me()
    log(f"Bot Client connected successfully as @{bot_info.username}!")

    await asyncio.gather(
        scan_photos_cycle(),
        scan_music_cycle(),
        publisher_worker()
    )

if __name__ == '__main__':
    asyncio.run(main())
