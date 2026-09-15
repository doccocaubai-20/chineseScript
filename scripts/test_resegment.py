import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from google import genai

sys.stdout.reconfigure(encoding='utf-8')

backend_dir = Path(r'c:\Users\admin\Documents\flashcard\flashcard-backend')
load_dotenv(backend_dir / '.env')
api_key = os.getenv('GEMINI_API_KEY')
client = genai.Client(api_key=api_key)

with open(backend_dir / 'data' / 'video-lessons' / 'vhsPRlbzaac.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Take first 5 segments
sample_segs = data['segments'][:5]
print("--- ORIGINAL RAW SEGMENTS ---")
for s in sample_segs:
    print(f"#{s['id']} [{s['start']}s - {s['end']}s] ({len(s['hanzi'])} chars): {s['hanzi']}")

prompt = f"""Bạn là Chuyên gia Biên tập Phụ đề Sư phạm Tiếng Trung Quốc tế.
Dưới đây là 5 câu phụ đề thô bị lỗi nghiêm trọng của một bài học video:
- Quá dài (trên 35-40 chữ/câu), gây khó khăn cho người học không biết chữ đang đọc ở đâu.
- Bị ngắt sai ngữ pháp, chặt đôi từ ghép ở ranh giới giữa các câu (ví dụ câu trước bị cắt cụt, từ bị xé làm đôi sang câu sau).

[DỮ LIỆU CÂU GỐC]
{json.dumps(sample_segs, ensure_ascii=False, indent=2)}

[YÊU CẦU TÁI CẤU TRÚC]
1. Hãy chia lại toàn bộ nội dung thành các vế câu ngắn gọn, chuẩn mực sư phạm (độ dài lý tưởng: 6 đến 15 chữ Hán/câu).
2. Tách theo dấu phẩy '，', dấu chấm '。', dấu hỏi '？'. Tuyệt đối không chặt đôi từ ghép.
3. Phân bổ thời gian (start, end) số thập phân chính xác cho từng câu ngắn sao cho khớp với luồng thời gian thực tế từ {sample_segs[0]['start']}s đến {sample_segs[-1]['end']}s.
4. Cung cấp câu tiếng Trung chuẩn ("hanzi"), bản dịch tiếng Việt tương ứng ("vi").

Trả về DUY NHẤT một JSON array:
[
  {{
    "start": 6.1,
    "end": 8.5,
    "hanzi": "大家好，欢迎回到每天中文，",
    "vi": "Chào mọi người, chào mừng quay trở lại với Tiếng Trung Mỗi Ngày,"
  }}
]
"""

res = client.models.generate_content(
    model='gemini-3.5-flash-lite',
    contents=prompt,
    config={"response_mime_type": "application/json"}
)

parsed = json.loads(res.text.strip())
print("\n--- RE-SEGMENTED SMART SEGMENTS ---")
for i, s in enumerate(parsed):
    dur = round(s['end'] - s['start'], 2)
    print(f"#{i+1} [{s['start']}s - {s['end']}s] ({dur}s, {len(s['hanzi'])} chars): {s['hanzi']}")
    print(f"    VI: {s['vi']}")
