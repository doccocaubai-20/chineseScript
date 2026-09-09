# Chạy Whisper trên Google Colab

Colab chỉ xử lý Whisper. Máy local vẫn tải audio, chạy FFmpeg, Pinyin, dịch và lưu database.

## 1. Tạo notebook Colab

Chọn `Runtime -> Change runtime type -> T4 GPU` nếu tài khoản có GPU.

Chạy các cell sau:

```python
!git clone https://github.com/doccocaubai-20/chineseScript.git
%cd chineseScript
!pip install -r services/ai-worker/requirements.txt python-multipart pyngrok
```

```python
import os
os.environ["WHISPER_MODEL"] = "small"
os.environ["WHISPER_DEVICE"] = "cuda"
os.environ["WHISPER_COMPUTE_TYPE"] = "float16"
os.environ["AUDIO_CHUNK_DURATION_SEC"] = "600"
os.environ["TRANSCRIBE_TOKEN"] = "replace-with-a-random-token"
```

```python
%cd services/ai-worker
!uvicorn colab_transcriber:app --host 0.0.0.0 --port 8000
```

Trong một cell khác, expose server bằng ngrok:

```python
from pyngrok import ngrok
public_url = ngrok.connect(8000)
print(public_url)
```

Nếu ngrok yêu cầu authentication, cấu hình `ngrok.set_auth_token(...)` trước khi connect.

## 2. Nối API local vào Colab

Trong file `.env` local, đặt URL đầy đủ của endpoint:

```env
REMOTE_TRANSCRIBE_URL=https://YOUR-NGROK-URL.ngrok-free.app/transcribe-upload
REMOTE_TRANSCRIBE_TOKEN=replace-with-the-same-random-token
```

Giữ nguyên:

```env
AI_WORKER_URL=http://127.0.0.1:8000
```

Như vậy `/youtube/download`, FFmpeg, `/align`, `/pinyin` và `/translate` vẫn chạy local; riêng WAV sẽ được upload sang Colab cho Whisper.

## 3. Khởi động lại API

```powershell
.\scripts\stop-local.ps1
.\scripts\start-local.ps1
```

Kiểm tra endpoint Colab trước khi chạy pipeline:

```powershell
Invoke-RestMethod https://YOUR-NGROK-URL.ngrok-free.app/health
```

Không commit token hoặc URL riêng tư vào Git. Mỗi lần Colab restart, cần chạy lại server và cập nhật URL ngrok nếu URL thay đổi.
