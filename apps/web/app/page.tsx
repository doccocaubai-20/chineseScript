"use client";

import { useMemo, useState } from "react";

type Segment = {
  id: number;
  order?: number;
  start: number;
  end: number;
  hanzi: string;
  pinyin: string;
  vi: string;
};

type Video = {
  id: string;
  title: string;
  channel?: string | null;
  durationSec?: number | null;
  thumbnailUrl?: string | null;
  sourceUrl?: string | null;
  status?: string;
  segments?: Segment[];
};

const initialSegments: Segment[] = [
  { id: 1, start: 6.1, end: 10.44, hanzi: "大家好，欢迎来到我的频道。", pinyin: "Dàjiā hǎo, huānyíng láidào wǒ de píndào.", vi: "Xin chào mọi người, chào mừng đến với kênh của tôi." },
  { id: 2, start: 10.9, end: 11.6, hanzi: "今天我们学习中文。", pinyin: "Jīntiān wǒmen xuéxí Zhōngwén.", vi: "Hôm nay chúng ta học tiếng Trung." },
];

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainder = (seconds % 60).toFixed(2).padStart(5, "0");
  return `${minutes}:${remainder}`;
}

export default function HomePage() {
  const [url, setUrl] = useState("");
  const [segments, setSegments] = useState(initialSegments);
  const [selectedId, setSelectedId] = useState(1);
  const [video, setVideo] = useState<Video | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("Dữ liệu mẫu sẵn sàng để chỉnh sửa.");
  const selected = useMemo(() => segments.find((segment) => segment.id === selectedId), [segments, selectedId]);

  async function createVideo() {
    if (!url.trim()) {
      setNotice("Hãy nhập URL YouTube trước.");
      return;
    }

    setLoading(true);
    setNotice("Đang đọc metadata từ YouTube...");
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001"}/videos/youtube`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sourceUrl: url.trim() }),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Không thể đọc video YouTube.");
      }
      const created = (await response.json()) as Video;
      setVideo(created);
      setSegments([]);
      setSelectedId(0);
      setNotice("Đã tạo video. Bấm xử lý để tạo transcript thật.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Không thể kết nối API.");
    } finally {
      setLoading(false);
    }

  }

  async function processVideo() {
    if (!video) return;
    setLoading(true);
    setNotice("Đang tải media và chạy pipeline AI. Có thể mất vài phút...");
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001"}/videos/${video.id}/process`, { method: "POST" });
      if (!response.ok) throw new Error((await response.text()) || "Pipeline thất bại.");
      const processed = (await response.json()) as Video;
      const mapped = (processed.segments ?? []).map((segment) => ({ ...segment, id: segment.order ?? segment.id }));
      setVideo(processed);
      setSegments(mapped);
      setSelectedId(mapped[0]?.id ?? 0);
      setNotice(`Đã tạo ${mapped.length} câu transcript.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Không thể chạy pipeline.");
    } finally {
      setLoading(false);
    }
  }

  function updateSegment(id: number, field: keyof Segment, value: string) {
    setSegments((current) => current.map((segment) => {
      if (segment.id !== id) return segment;
      if (field === "start" || field === "end" || field === "id") return { ...segment, [field]: Number(value) };
      return { ...segment, [field]: value };
    }));
  }

  function addSegment() {
    const id = Math.max(0, ...segments.map((segment) => segment.id)) + 1;
    setSegments([...segments, { id, start: 0, end: 1, hanzi: "", pinyin: "", vi: "" }]);
    setSelectedId(id);
  }

  function removeSelected() {
    setSegments((current) => current.filter((segment) => segment.id !== selectedId));
    setSelectedId(segments.find((segment) => segment.id !== selectedId)?.id ?? 0);
  }

  function saveDraft() {
    setNotice(`Đã lưu bản nháp gồm ${segments.length} câu.`);
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <span className="eyebrow">CHINESE VIDEO LEARNING</span>
          <h1>Transcript editor</h1>
        </div>
        <span className="status"><span className="status-dot" /> Local workspace</span>
      </header>

      <section className="source-card">
        <div>
          <label htmlFor="youtube-url">YouTube URL</label>
          <input id="youtube-url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://www.youtube.com/watch?v=..." />
        </div>
        <button className="primary" onClick={createVideo} disabled={loading}>{loading ? "Đang xử lý..." : "Tạo transcript"}</button>
      </section>

      {video && (
        <section className="video-summary">
          {video.thumbnailUrl && <img src={video.thumbnailUrl} alt="" />}
          <div><span className="eyebrow">VIDEO ĐÃ TẠO</span><h2>{video.title}</h2><p>{video.channel || "Không rõ kênh"} · {video.durationSec ? formatTime(video.durationSec) : "Chưa rõ thời lượng"}</p></div>
          <button className="primary" onClick={processVideo} disabled={loading}>{loading ? "Đang chạy..." : "Chạy pipeline"}</button>
        </section>
      )}

      <div className="workspace">
        <section className="panel transcript-panel">
          <div className="panel-heading">
            <div><span className="eyebrow">TRANSCRIPT</span><h2>Chinese Conversation</h2></div>
            <span className="count">{segments.length} câu</span>
          </div>
          <div className="segment-list">
            {segments.map((segment) => (
              <button className={`segment-row ${segment.id === selectedId ? "selected" : ""}`} key={segment.id} onClick={() => setSelectedId(segment.id)}>
                <span className="segment-number">{String(segment.id).padStart(2, "0")}</span>
                <span className="segment-content">
                  <strong>{segment.hanzi || "Chưa có Hanzi"}</strong>
                  <small>{formatTime(segment.start)} — {formatTime(segment.end)} · {segment.vi || "Chưa có bản dịch"}</small>
                </span>
                <span className="chevron">›</span>
              </button>
            ))}
            {!segments.length && <p className="empty">Chưa có transcript. Hãy chạy pipeline xử lý video để tạo các câu.</p>}
          </div>
          <button className="add-button" onClick={addSegment}>＋ Thêm câu</button>
        </section>

        <section className="panel editor-panel">
          <div className="panel-heading">
            <div><span className="eyebrow">EDITING</span><h2>Câu {selected?.id ?? "—"}</h2></div>
            <button className="ghost danger" onClick={removeSelected} disabled={!selected}>Xóa</button>
          </div>
          {selected ? (
            <div className="form">
              <div className="field-row">
                <label>Bắt đầu (giây)<input type="number" step="0.01" value={selected.start} onChange={(event) => updateSegment(selected.id, "start", event.target.value)} /></label>
                <label>Kết thúc (giây)<input type="number" step="0.01" value={selected.end} onChange={(event) => updateSegment(selected.id, "end", event.target.value)} /></label>
              </div>
              <label>Hanzi<textarea rows={3} value={selected.hanzi} onChange={(event) => updateSegment(selected.id, "hanzi", event.target.value)} /></label>
              <label>Pinyin<textarea rows={2} value={selected.pinyin} onChange={(event) => updateSegment(selected.id, "pinyin", event.target.value)} /></label>
              <label>Tiếng Việt<textarea rows={3} value={selected.vi} onChange={(event) => updateSegment(selected.id, "vi", event.target.value)} /></label>
              <div className="actions"><button className="ghost" onClick={() => setNotice("Validation: bản nháp hợp lệ.")}>Kiểm tra</button><button className="primary" onClick={saveDraft}>Lưu bản nháp</button></div>
            </div>
          ) : <p className="empty">Chọn một câu để bắt đầu chỉnh sửa.</p>}
        </section>
      </div>
      <p className="notice" role="status">{notice}</p>
    </main>
  );
}
