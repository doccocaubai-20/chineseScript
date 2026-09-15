import os
import sys
import json
import time
import re
from pathlib import Path
from dotenv import load_dotenv
from pypinyin import Style, lazy_pinyin
from google import genai

sys.stdout.reconfigure(encoding='utf-8')

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CURRENT_DIR.parent
WORKSPACE_ROOT = PROJECT_DIR.parent
BACKEND_DIR = WORKSPACE_ROOT / "flashcard-backend"
VIDEO_LESSONS_DIR = BACKEND_DIR / "data" / "video-lessons"

load_dotenv(PROJECT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not GEMINI_API_KEY:
    print("[ERROR] GEMINI_API_KEY not found!")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "gemini-3.5-flash-lite"

def add_pinyin(text: str) -> str:
    syllables = lazy_pinyin(
        text,
        style=Style.TONE,
        neutral_tone_with_five=True,
        errors=lambda item: list(item),
    )
    return " ".join(syllables).replace("  ", " ").strip()

def clean_hanzi_only(text: str) -> str:
    # Remove any stray Latin/Vietnamese characters accidentally returned by LLM
    text = re.sub(r"[a-zA-ZÀ-ỹ/]", "", text)
    return "".join(text.split()).strip()

def repair_segment_batch(raw_batch):
    start_time = raw_batch[0]["start"]
    end_time = raw_batch[-1]["end"]

    prompt = f"""Bạn là Chuyên gia Biên tập Phụ đề Sư phạm Tiếng Trung Quốc tế.
Dưới đây là một đoạn phụ đề thô trích xuất từ audio bị lỗi:
1. Quá dài (trên 30-40 chữ/câu), gây khó khăn cho học viên theo dõi chữ Hán trên màn hình.
2. Bị chèn dấu chấm giả '。' làm chặt đôi từ ghép hoặc cụm từ giữa các câu (ví dụ '形式的。' bị ngắt khỏi '内卷', '成就。' bị ngắt khỏi '感', '关面选。' bị ngắt khỏi '择躺平').
3. Thiếu dấu phẩy phân tách vế câu tự nhiên.

[DỮ LIỆU CÂU THÔ]
{json.dumps(raw_batch, ensure_ascii=False, indent=2)}

[YÊU CẦU TÁI CẤU TRÚC]
1. HÃY HÀN GẮN LẠI các từ vựng/cụm từ bị chặt đôi, bỏ các dấu chấm sai giữa chừng để thành câu văn chuẩn chỉnh ngữ pháp.
2. CHIA LẠI thành các vế câu ngắn gọn, chuẩn mực sư phạm:
   - Độ dài lý tưởng: 6 đến 16 chữ Hán/câu (tương đương 2 đến 4.5 giây).
   - Tách câu tự nhiên tại các dấu phẩy '，', dấu chấm '。', dấu hỏi '？'.
3. TUYỆT ĐỐI trường "hanzi" CHỈ chứa chữ Hán và dấu câu tiếng Trung (，。？！…：“”). KHÔNG ĐƯỢC chứa chữ Latinh, tiếng Việt, hoặc chú thích dịch thuật bên trong "hanzi".
4. Phân bổ thời gian ("start", "end") số thập phân chính xác cho từng câu ngắn sao cho khớp liên tục từ {start_time}s đến {end_time}s.
5. Dịch nghĩa tiếng Việt tương ứng ("vi") tự nhiên, thuần Việt, mượt mà.

Trả về DUY NHẤT một JSON array:
[
  {{
    "start": {start_time},
    "end": ...,
    "hanzi": "...",
    "vi": "..."
  }}
]
"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            parsed = json.loads(res.text.strip())
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed
        except Exception as e:
            print(f"  [WARN] Gemini retry {attempt+1}/{max_retries}: {e}")
            time.sleep(2)

    # Fallback to original if Gemini failed
    return raw_batch

def split_clause(hanzi: str, max_chars: int = 18):
    if len(hanzi) <= max_chars:
        return [hanzi]
    parts = [p for p in re.split(r'([，。！？；、])', hanzi) if p]
    chunks = []
    curr = ""
    for i in range(0, len(parts), 2):
        clause = parts[i] + (parts[i+1] if i+1 < len(parts) else '')
        if not curr:
            curr = clause
        elif len(curr) + len(clause) <= max_chars:
            curr += clause
        else:
            chunks.append(curr)
            curr = clause
    if curr:
        chunks.append(curr)
    return chunks if chunks else [hanzi]

def translate_batch(batch_items):
    prompt = f"""Dịch các vế câu tiếng Trung ngắn sau đây sang tiếng Việt tự nhiên, phù hợp người học tiếng:
{json.dumps([{'id': x['id'], 'hanzi': x['hanzi']} for x in batch_items], ensure_ascii=False, indent=2)}
YÊU CẦU:
1. Trả về DUY NHẤT một JSON array: [{{"id": number, "vi": "Bản dịch tiếng Việt"}}]
2. Nếu có từ cần đặt trong ngoặc thì dùng dấu ngoặc đơn '...' thay vì ngoặc kép để tránh lỗi JSON.
3. Bản dịch súc tích, chuẩn nghĩa theo đúng vế câu.
"""
    for attempt in range(3):
        try:
            res = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            raw = res.text.strip()
            # Clean possible escaped quotes
            parsed = json.loads(raw)
            return {item["id"]: item["vi"].strip() for item in parsed if "id" in item and "vi" in item}
        except Exception as e:
            print(f"  [WARN] Sub-clause translation retry {attempt+1}: {e}")
            time.sleep(2)
    return {}

def repair_video_json(json_path: Path):
    print(f"\n=======================================================")
    print(f"[REPAIR] Processing: {json_path.name}")
    print(f"=======================================================")

    backup_path = json_path.with_suffix(".json.bak")
    source_path = backup_path if backup_path.exists() else json_path

    with open(source_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # If backup doesn't exist yet, create it from original
    if not backup_path.exists():
        import shutil
        shutil.copy2(json_path, backup_path)
        print(f"  [BACKUP] Created backup -> {backup_path.name}")

    old_segments = data.get("segments", [])
    print(f"  Total raw segments to process: {len(old_segments)} (from {source_path.name})")

    # Step 1: Broad Gemini re-segmentation to heal broken phrases and establish structure
    BATCH_SIZE = 25
    new_segments_raw = []

    total_batches = -(-len(old_segments) // BATCH_SIZE)
    for i in range(0, len(old_segments), BATCH_SIZE):
        batch = old_segments[i : i + BATCH_SIZE]
        batch_idx = i // BATCH_SIZE + 1
        print(f"  [Step 1/3] Gemini contextual pass {batch_idx} / {total_batches} (seg #{batch[0].get('id')} to #{batch[-1].get('id')})...")
        repaired = repair_segment_batch(batch)
        new_segments_raw.extend(repaired)
        time.sleep(1)

    # Step 2: Fine-grained clause splitting (strictly max 18 chars for easy visual tracking)
    print(f"  [Step 2/3] Splitting long clauses into bite-sized units (<= 18 chars)...")
    split_segments = []
    needs_trans_items = []

    for seg in new_segments_raw:
        hanzi = clean_hanzi_only(seg.get("hanzi", "").strip())
        if not hanzi:
            continue
        start = round(float(seg["start"]), 2)
        end = round(float(seg["end"]), 2)
        duration = max(0.2, end - start)
        sub_clauses = split_clause(hanzi, max_chars=18)

        if len(sub_clauses) == 1:
            split_segments.append({
                "start": start,
                "end": end,
                "hanzi": hanzi,
                "vi": seg.get("vi", "").strip(),
            })
        else:
            total_chars = sum(len(c) for c in sub_clauses)
            cur_time = start
            for idx, c in enumerate(sub_clauses):
                frac = len(c) / total_chars
                c_dur = duration * frac
                c_end = cur_time + c_dur if idx < len(sub_clauses) - 1 else end
                c_item = {
                    "temp_id": len(needs_trans_items) + 1,
                    "start": round(cur_time, 2),
                    "end": round(c_end, 2),
                    "hanzi": c,
                    "vi": "",
                }
                split_segments.append(c_item)
                needs_trans_items.append(c_item)
                cur_time = c_end

    # Step 3: Batch translate newly split short clauses if any
    if needs_trans_items:
        print(f"  [Step 3/3] Translating {len(needs_trans_items)} refined sub-clauses with Gemini...")
        TRANS_BATCH_SIZE = 25
        for b_idx in range(0, len(needs_trans_items), TRANS_BATCH_SIZE):
            chunk = needs_trans_items[b_idx : b_idx + TRANS_BATCH_SIZE]
            t_map = translate_batch([{"id": x["temp_id"], "hanzi": x["hanzi"]} for x in chunk])
            for x in chunk:
                if x["temp_id"] in t_map:
                    x["vi"] = t_map[x["temp_id"]]
            time.sleep(1)

    # Step 4: Final formatting with clean pinyin and sequential IDs
    final_segments = []
    for idx, seg in enumerate(split_segments):
        hanzi = seg["hanzi"]
        final_segments.append({
            "id": idx + 1,
            "start": round(float(seg["start"]), 2),
            "end": round(float(seg["end"]), 2),
            "hanzi": hanzi,
            "pinyin": add_pinyin(hanzi),
            "vi": seg.get("vi", "").strip(),
        })

    data["totalSentences"] = len(final_segments)
    data["segments"] = final_segments

    # Backup original file
    backup_path = json_path.with_suffix(".json.bak")
    if not backup_path.exists():
        import shutil
        shutil.copy2(json_path, backup_path)
        print(f"  [BACKUP] Created backup -> {backup_path.name}")

    # Overwrite with clean repaired JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  [SUCCESS] Repaired {json_path.name}: {len(old_segments)} raw chunks -> {len(final_segments)} clean bite-sized sentences!")

def main():
    if len(sys.argv) > 1:
        target_name = sys.argv[1]
        if not target_name.endswith(".json"):
            target_name += ".json"
        target_file = VIDEO_LESSONS_DIR / target_name
        if not target_file.exists():
            target_file = PROJECT_DIR / "output" / target_name
        if not target_file.exists():
            print(f"[ERROR] File not found: {target_name}")
            sys.exit(1)
        repair_video_json(target_file)
    else:
        # Default: repair vhsPRlbzaac.json
        target_file = VIDEO_LESSONS_DIR / "vhsPRlbzaac.json"
        if target_file.exists():
            repair_video_json(target_file)
        else:
            print("[ERROR] Please provide video JSON filename.")

if __name__ == "__main__":
    main()
