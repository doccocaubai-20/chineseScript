import os
import sys
import json
import re
import time
import shutil
import argparse
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Ensure UTF-8 stdout on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import yt_dlp
from pypinyin import Style, lazy_pinyin
from faster_whisper import WhisperModel
from google import genai

# 1. Directories setup
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CURRENT_DIR.parent  # ToolsYTB/
WORKSPACE_ROOT = PROJECT_DIR.parent  # flashcard/
BACKEND_DIR = WORKSPACE_ROOT / "flashcard-backend"

DEFAULT_OUTPUT_DIR = PROJECT_DIR / "output"
DEFAULT_MEDIA_TEMP = PROJECT_DIR / "media" / "temp"
APP_DATA_DIR = BACKEND_DIR / "data" / "video-lessons"

# Load environment variables
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")

GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
)

# 2. Text Segmentation & Pinyin Logic
SENTENCE_ENDINGS = set("。！？!?；;\n")
CLAUSE_ENDINGS = set("，,、:：")
PUNCTUATION_REPLACEMENTS = str.maketrans({",": "，", "?": "？", "!": "！"})

def clean_hanzi(text: str) -> str:
    cleaned = re.sub(r"\s+", "", text).translate(PUNCTUATION_REPLACEMENTS)
    return cleaned

def align_whisper_segments(chunks, max_duration=4.5, max_chars=16, min_chars=6):
    """
    Groups word-level timestamps from faster-whisper into natural, pedagogical Chinese clauses.
    Target: 6 to 16 characters per segment (~2 to 4.5s) for optimal reading and shadowing.
    """
    aligned = []
    current_words = []

    def flush():
        if not current_words:
            return
        text = clean_hanzi("".join(str(w.get("text", "")) for w in current_words))
        if text:
            aligned.append({
                "start": float(current_words[0]["start"]),
                "end": float(current_words[-1]["end"]),
                "hanzi": text,
            })
        current_words.clear()

    for chunk in chunks:
        words = chunk.get("words") or []
        if not words:
            flush()
            text = clean_hanzi(str(chunk.get("text", "")))
            if text and float(chunk.get("start", 0)) < float(chunk.get("end", 0)):
                aligned.append({
                    "start": float(chunk["start"]),
                    "end": float(chunk["end"]),
                    "hanzi": text,
                })
            continue

        for word in words:
            word_text = str(word.get("text", "")).strip()
            if not word_text:
                continue

            if current_words:
                prev_end = float(current_words[-1].get("end", 0))
                cur_start = float(current_words[0].get("start", 0))
                cur_text = "".join(str(item.get("text", "")) for item in current_words)
                cur_chars = len(re.sub(r"[^\u4e00-\u9fff]", "", cur_text))
                cur_dur = float(word.get("end", cur_start)) - cur_start
                pause = float(word.get("start", prev_end)) - prev_end
                prev_last_char = cur_text[-1] if cur_text else ""

                # Split conditions:
                # 1. Previous word ended with full stop (。！？)
                # 2. Previous word ended with comma (，、) AND accumulated >= min_chars
                # 3. Acoustic pause >= 0.4s AND accumulated >= min_chars
                # 4. Accumulated >= max_chars OR duration >= max_duration (split cleanly at word boundary)
                if (
                    prev_last_char in SENTENCE_ENDINGS
                    or (prev_last_char in CLAUSE_ENDINGS and cur_chars >= min_chars)
                    or (pause >= 0.4 and cur_chars >= min_chars)
                    or cur_chars >= max_chars
                    or cur_dur >= max_duration
                ):
                    flush()

            current_words.append(word)
            # If the current word ends with an explicit sentence ending, flush
            if any(mark in word_text for mark in SENTENCE_ENDINGS):
                flush()

    flush()

    # Post-process into final segments with sequential 1-based IDs
    result = []
    prev_end = -1.0
    for seg in aligned:
        start = max(0.0, seg["start"])
        end = max(start, seg["end"])
        if end <= start or start < prev_end - 0.25:
            continue
        result.append({
            "id": len(result) + 1,
            "start": round(start, 2),
            "end": round(end, 2),
            "hanzi": seg["hanzi"],
        })
        prev_end = end

    return result

def add_pinyin(segments):
    """Generates accurate tone-marked Pinyin for each Chinese segment."""
    for seg in segments:
        hanzi = seg["hanzi"]
        syllables = lazy_pinyin(
            hanzi,
            style=Style.TONE,
            neutral_tone_with_five=True,
            errors=lambda item: list(item),
        )
        pinyin_str = " ".join(syllables).replace("  ", " ").strip()
        seg["pinyin"] = pinyin_str
    return segments

# 3. Gemini Translation & Metadata Generator
def translate_segments_with_gemini(client, segments, gemini_model="gemini-3.5-flash-lite", batch_size=25):
    """
    Translates Chinese segments to fluent Vietnamese using Gemini API in batches.
    """
    translated_map = {}
    
    for i in range(0, len(segments), batch_size):
        batch = segments[i:i+batch_size]
        batch_payload = [{"id": s["id"], "hanzi": s["hanzi"]} for s in batch]
        
        prompt = f"""Bạn là một dịch giả Hán - Việt chuyên nghiệp và giàu kinh nghiệm sư phạm.
Nhiệm vụ: Hãy dịch các câu tiếng Trung sau đây sang tiếng Việt tự nhiên, mượt mà, đúng ngữ cảnh bài học video.
YÊU CẦU:
1. Trả về DUY NHẤT một JSON array chứa các object: {{"id": number, "vi": "Bản dịch tiếng Việt"}}.
2. Giữ nguyên chính xác số lượng câu và giá trị "id" tương ứng. Không thêm bớt câu.
3. Bản dịch thuần Việt, câu văn tự nhiên, không dịch máy thô cứng.

Input:
{json.dumps(batch_payload, ensure_ascii=False)}
"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                res = client.models.generate_content(
                    model=gemini_model,
                    contents=prompt,
                    config={"response_mime_type": "application/json"}
                )
                raw = res.text.strip()
                parsed = json.loads(raw)
                for item in parsed:
                    if isinstance(item, dict) and "id" in item and "vi" in item:
                        translated_map[item["id"]] = item["vi"].strip()
                break
            except Exception as e:
                print(f"    [WARN] Gemini translation retry {attempt+1}/{max_retries} for batch {i//batch_size + 1}: {e}")
                time.sleep(2)
        time.sleep(1)  # Respect RPM limits

    # Merge translations back into segments
    for s in segments:
        s["vi"] = translated_map.get(s["id"], s["hanzi"])

    return segments

def generate_video_metadata_with_gemini(client, raw_title, channel_name, sample_hanzi_text, gemini_model="gemini-3.5-flash-lite"):
    """
    Generates Vietnamese title, Chinese title, Topic and estimated HSK level.
    """
    prompt = f"""Dựa vào thông tin video học tiếng Trung sau:
- Tiêu đề gốc YouTube: {raw_title}
- Kênh: {channel_name}
- Đoạn trích nội dung bài nói: {sample_hanzi_text[:300]}

Hãy trả về một JSON object với các trường:
{{
  "title": "Tiêu đề tiếng Việt ngắn gọn, hấp dẫn cho bài học",
  "titleHanzi": "Tiêu đề tiếng Trung súc tích",
  "level": 2, // Ước lượng cấp độ HSK từ 1 đến 6 (số nguyên)
  "topic": "Chủ đề bài học (VD: Đời sống, Giao tiếp, Ẩm thực, Du lịch, Podcast, Phim ảnh...)"
}}
"""
    try:
        res = client.models.generate_content(
            model=gemini_model,
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        data = json.loads(res.text.strip())
        return {
            "title": data.get("title") or raw_title,
            "titleHanzi": data.get("titleHanzi") or raw_title,
            "level": int(data.get("level", 2)),
            "topic": data.get("topic") or "Đời sống",
        }
    except Exception as e:
        print(f"    [WARN] Gemini metadata generation fallback: {e}")
        return {
            "title": raw_title,
            "titleHanzi": raw_title,
            "level": 2,
            "topic": "Đời sống",
        }

# 4. YouTube Channel / Playlist Scraper
def get_channel_videos(channel_url, limit=10):
    """
    Scrapes video metadata from a YouTube channel/playlist using yt-dlp without downloading.
    """
    print(f"\n[SCAN] Fetching video list from: {channel_url} (Limit: {limit})...")
    ydl_opts = {
        "extract_flat": True,
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }
    videos = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
        entries = info.get("entries") or []
        for entry in entries:
            if not entry:
                continue
            v_id = entry.get("id")
            v_url = entry.get("url") or f"https://www.youtube.com/watch?v={v_id}"
            title = entry.get("title") or "Video bài học"
            duration = entry.get("duration") or 0
            if v_id:
                videos.append({
                    "id": v_id,
                    "url": v_url,
                    "title": title,
                    "duration": duration,
                    "channel": info.get("channel") or info.get("uploader") or entry.get("uploader") or "YouTube",
                    "thumbnail": entry.get("thumbnail") or f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg",
                })
            if len(videos) >= limit * 3:  # Fetch a few extra to account for duration filtering
                break

    return videos

# 5. Core Video Processor
def process_single_video(video_info, whisper_model_instance, gemini_client, gemini_model, output_dir, sync_dir):
    v_id = video_info["id"]
    v_url = video_info["url"]
    v_title = video_info["title"]
    
    json_filename = f"{v_id}.json"
    target_json_path = output_dir / json_filename
    app_json_path = sync_dir / json_filename if sync_dir else None

    # Check if already processed
    if target_json_path.exists() or (app_json_path and app_json_path.exists()):
        print(f"  [SKIP] Video {v_id} ({v_title[:30]}...) already processed.")
        return True

    print(f"\n=======================================================")
    print(f"[PROCESS] Starting: {v_title}")
    print(f"  ID: {v_id} | URL: {v_url}")
    print(f"=======================================================")

    temp_dir = DEFAULT_MEDIA_TEMP / v_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    download_template = str(temp_dir / "%(id)s.%(ext)s")

    try:
        # Step 1: Download audio stream only (fast & lightweight)
        print("  [1/6] Downloading audio stream via yt-dlp...")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": download_template,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 60,
            "retries": 3,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            meta = ydl.extract_info(v_url, download=True)
            downloaded_file = ydl.prepare_filename(meta)

        # Step 2: Convert to 16kHz mono WAV using ffmpeg for Whisper
        print("  [2/6] Normalizing audio (16kHz mono WAV via FFmpeg)...")
        wav_path = temp_dir / f"{v_id}_16k.wav"
        cmd = [
            "ffmpeg", "-y",
            "-i", downloaded_file,
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(wav_path)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # Step 3: Transcribe with faster-whisper (Chinese, word-level timestamps)
        print("  [3/6] Transcribing Chinese speech via faster-whisper...")
        t_start = time.time()
        segments_iter, whisper_info = whisper_model_instance.transcribe(
            str(wav_path),
            language="zh",
            initial_prompt="这是一段普通话中文播客，请务必输出规范的中文标点符号，包括逗号、句号、顿号、问号和感叹号。",
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=400),
        )
        
        chunks = []
        for s in segments_iter:
            words = []
            if s.words:
                for w in s.words:
                    words.append({
                        "text": w.word,
                        "start": w.start,
                        "end": w.end,
                    })
            chunks.append({
                "start": s.start,
                "end": s.end,
                "text": s.text,
                "words": words,
            })
        print(f"  -> Transcribed {len(chunks)} raw audio chunks in {time.time()-t_start:.1f}s.")

        # Step 4: Align into natural sentences
        print("  [4/6] Aligning sentence boundaries & generating Pinyin...")
        aligned = align_whisper_segments(chunks)
        if not aligned:
            print("  [ERROR] No valid speech segments recognized.")
            return False

        segments = add_pinyin(aligned)
        print(f"  -> Generated {len(segments)} clean, timestamped learning sentences.")

        # Step 5: Translate to Vietnamese with Gemini 3.5 Flash
        print(f"  [5/6] Translating {len(segments)} segments to Vietnamese with Gemini ({gemini_model})...")
        t_trans = time.time()
        translated_segments = translate_segments_with_gemini(gemini_client, segments, gemini_model=gemini_model)
        print(f"  -> Translation finished in {time.time()-t_trans:.1f}s.")

        # Step 6: Generate metadata (HSK Level, Topic, Title)
        sample_text = "".join(s["hanzi"] for s in translated_segments[:10])
        meta_info = generate_video_metadata_with_gemini(
            gemini_client,
            v_title,
            video_info.get("channel", "YouTube"),
            sample_text,
            gemini_model=gemini_model
        )

        duration_sec = int(whisper_info.duration) if hasattr(whisper_info, 'duration') and whisper_info.duration else video_info.get("duration", 0)

        # Assemble final JSON contract
        learning_json = {
            "id": v_id,
            "youtubeId": v_id,
            "title": meta_info["title"],
            "titleHanzi": meta_info["titleHanzi"],
            "level": meta_info["level"],
            "topic": meta_info["topic"],
            "channel": video_info.get("channel", "Chinese Channel"),
            "durationSec": duration_sec,
            "thumbnailUrl": video_info.get("thumbnail") or f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg",
            "totalSentences": len(translated_segments),
            "segments": translated_segments,
        }

        # Save to output directory
        with open(target_json_path, "w", encoding="utf-8") as f:
            json.dump(learning_json, f, ensure_ascii=False, indent=2)
        print(f"  [SUCCESS] Saved JSON -> {target_json_path}")

        # Sync directly to ChongZi App if path exists
        if app_json_path:
            with open(app_json_path, "w", encoding="utf-8") as f:
                json.dump(learning_json, f, ensure_ascii=False, indent=2)
            print(f"  [SYNCED] Auto-synced to ChongZi App -> {app_json_path}")

        return True

    except Exception as e:
        print(f"  [FAILED] Error processing video {v_id}: {e}")
        return False

    finally:
        # Cleanup temporary audio files to keep disk clean
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

# 6. Main CLI Entrypoint
def main():
    parser = argparse.ArgumentParser(
        description="Auto-fetch YouTube Channel Videos -> Transcribe (Whisper) -> Translate (Gemini 3.5 Flash) -> Export Learning JSON"
    )
    parser.add_argument("--channel", "-c", required=True, help="YouTube Channel / Playlist URL or single Video URL")
    parser.add_argument("--limit", "-l", type=int, default=5, help="Maximum number of videos to process. Default: 5")
    parser.add_argument("--max-duration", type=int, default=900, help="Max duration in seconds (default: 900 = 15m)")
    parser.add_argument("--min-duration", type=int, default=30, help="Min duration in seconds (default: 30s to skip shorts)")
    parser.add_argument("--whisper-model", default="small", help="faster-whisper model size (small, base, tiny). Default: small")
    parser.add_argument("--whisper-device", default="cpu", help="Compute device for whisper (cpu or cuda). Default: cpu")
    parser.add_argument("--gemini-model", default="gemini-3.5-flash-lite", help="Gemini model for translation. Default: gemini-3.5-flash-lite")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to save JSON files")
    parser.add_argument("--no-sync", action="store_true", help="Disable auto-sync to flashcard-backend/data/video-lessons")

    args = parser.parse_args()

    if not GEMINI_API_KEY:
        print("[ERROR] GEMINI_API_KEY not found. Please set GEMINI_API_KEY in .env or flashcard-backend/.env")
        sys.exit(1)

    output_path = Path(args.output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    sync_path = APP_DATA_DIR if (not args.no_sync and APP_DATA_DIR.exists()) else None

    print(f"=======================================================")
    print(f"🚀 YOUTUBE CHANNEL TO CHONGZI VIDEO LESSONS GENERATOR")
    print(f"  Channel / Source: {args.channel}")
    print(f"  Limit: {args.limit} videos | Max Duration: {args.max_duration}s")
    print(f"  Whisper Model: {args.whisper_model} ({args.whisper_device})")
    print(f"  Translation AI: Google Gemini ({args.gemini_model})")
    print(f"  Output Dir: {output_path}")
    print(f"  App Sync: {'Enabled (' + str(sync_path) + ')' if sync_path else 'Disabled'}")
    print(f"=======================================================")

    # Initialize Gemini Client
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

    # Initialize Whisper Model (downloaded once and cached)
    print(f"\n[INIT] Loading faster-whisper ({args.whisper_model})...")
    whisper_model = WhisperModel(
        args.whisper_model,
        device=args.whisper_device,
        compute_type="int8" if args.whisper_device == "cpu" else "float16",
    )
    print("[INIT] Whisper model loaded successfully.")

    # Check if single video URL or Channel/Playlist
    raw_channel = args.channel.strip()
    if "watch?v=" in raw_channel or "youtu.be/" in raw_channel:
        # Single video mode
        ydl_opts = {"skip_download": True, "quiet": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            meta = ydl.extract_info(raw_channel, download=False)
            candidate_videos = [{
                "id": meta["id"],
                "url": raw_channel,
                "title": meta.get("title", "Video"),
                "duration": meta.get("duration", 0),
                "channel": meta.get("channel") or meta.get("uploader") or "YouTube",
                "thumbnail": meta.get("thumbnail"),
            }]
    else:
        # Channel / Playlist mode
        all_videos = get_channel_videos(raw_channel, limit=args.limit)
        candidate_videos = []
        for v in all_videos:
            dur = v.get("duration") or 0
            if dur > 0 and (dur < args.min_duration or dur > args.max_duration):
                print(f"  [FILTER] Skipping '{v['title'][:30]}...' (Duration: {dur}s not in [{args.min_duration}, {args.max_duration}])")
                continue
            candidate_videos.append(v)
            if len(candidate_videos) >= args.limit:
                break

    print(f"\n[QUEUE] Found {len(candidate_videos)} candidate videos to process.\n")

    success_count = 0
    for idx, vid in enumerate(candidate_videos):
        print(f"\n--- Progress: [{idx+1}/{len(candidate_videos)}] ---")
        ok = process_single_video(
            video_info=vid,
            whisper_model_instance=whisper_model,
            gemini_client=gemini_client,
            gemini_model=args.gemini_model,
            output_dir=output_path,
            sync_dir=sync_path,
        )
        if ok:
            success_count += 1

    print(f"\n=======================================================")
    print(f"🎉 BATCH COMPLETE: Successfully processed {success_count}/{len(candidate_videos)} videos!")
    print(f"📁 JSON files saved to: {output_path}")
    if sync_path:
        print(f"📱 Synced directly to ChongZi App at: {sync_path}")
        if success_count > 0:
            print(f"\n[SYNC] Auto-seeding {success_count} new videos into PostgreSQL Database...")
            try:
                subprocess.run(
                    ["npx", "ts-node", "prisma/seed_videos.ts"],
                    cwd=str(BACKEND_DIR),
                    shell=True,
                    check=True
                )
                print("  [SUCCESS] All video lessons seeded to Database successfully!")
            except Exception as e:
                print(f"  [WARN] Database auto-seed warning: {e}")
    print(f"=======================================================\n")

if __name__ == "__main__":
    main()
