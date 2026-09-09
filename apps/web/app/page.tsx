"use client";

import { useEffect, useMemo, useRef, useState } from "react";

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
  youtubeId?: string | null;
  title: string;
  channel?: string | null;
  durationSec?: number | null;
  thumbnailUrl?: string | null;
  sourceUrl?: string | null;
  status?: string;
  segments?: Segment[];
};

type ProcessingJob = {
  id: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
  currentStep?: string | null;
  progress: number;
  errorMessage?: string | null;
};

type YouTubePlayer = {
  seekTo: (seconds: number, allowSeekAhead?: boolean) => void;
  getCurrentTime: () => number;
  destroy: () => void;
};

type YouTubeApi = {
  Player: new (
    element: HTMLElement,
    options: {
      videoId: string;
      playerVars?: { modestbranding?: number; rel?: number };
      events?: { onReady?: () => void };
    },
  ) => YouTubePlayer;
};

declare global {
  interface Window {
    YT?: YouTubeApi;
    onYouTubeIframeAPIReady?: () => void;
  }
}

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
  const [activeSegmentId, setActiveSegmentId] = useState(0);
  const playerRef = useRef<YouTubePlayer | null>(null);
  const playerElementRef = useRef<HTMLDivElement | null>(null);
  const [notice, setNotice] = useState("Dữ liệu mẫu sẵn sàng để chỉnh sửa.");
  const [transcriptInput, setTranscriptInput] = useState<HTMLInputElement | null>(null);
  const selected = useMemo(() => segments.find((segment) => segment.id === selectedId), [segments, selectedId]);

  useEffect(() => {
    if (!video?.youtubeId || !playerElementRef.current) return;

    let cancelled = false;
    const createPlayer = () => {
      if (!cancelled && window.YT && playerElementRef.current) {
        playerRef.current?.destroy();
        playerRef.current = new window.YT.Player(playerElementRef.current, {
          videoId: video.youtubeId ?? "",
          playerVars: { modestbranding: 1, rel: 0 },
          events: { onReady: () => setNotice("Video đã sẵn sàng.") },
        });
      }
    };

    if (window.YT) {
      createPlayer();
    } else {
      const previousReady = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => {
        previousReady?.();
        createPlayer();
      };
      const script = document.querySelector('script[src="https://www.youtube.com/iframe_api"]');
      if (!script) {
        const apiScript = document.createElement("script");
        apiScript.src = "https://www.youtube.com/iframe_api";
        document.body.appendChild(apiScript);
      }
    }

    return () => {
      cancelled = true;
      playerRef.current?.destroy();
      playerRef.current = null;
    };
  }, [video?.youtubeId]);

  useEffect(() => {
    if (!playerRef.current || !segments.length) return;
    const timer = window.setInterval(() => {
      const currentTime = playerRef.current?.getCurrentTime() ?? -1;
      const currentSegment = segments.find(
        (segment) => currentTime >= segment.start && currentTime < segment.end,
      );
      if (currentSegment) {
        setActiveSegmentId(currentSegment.id);
        setSelectedId(currentSegment.id);
      }
    }, 300);
    return () => window.clearInterval(timer);
  }, [segments]);

  function seekToSegment(segment: Segment) {
    setSelectedId(segment.id);
    setActiveSegmentId(segment.id);
    playerRef.current?.seekTo(segment.start, true);
  }

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
      const mapped = (created.segments ?? []).map((segment) => ({
        ...segment,
        id: segment.order ?? segment.id,
      }));
      setVideo(created);
      setSegments(mapped);
      setSelectedId(mapped[0]?.id ?? 0);
      setNotice(mapped.length
        ? `Đã tải lại ${mapped.length} câu transcript từ database.`
        : "Đã tạo video. Bấm xử lý để tạo transcript thật.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Không thể kết nối API.");
    } finally {
      setLoading(false);
    }

  }

  async function processVideo() {
    if (!video) return;
    setLoading(true);
    setNotice("Đã xếp hàng pipeline AI...");
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001"}/videos/${video.id}/process`, { method: "POST" });
      if (!response.ok) throw new Error((await response.text()) || "Pipeline thất bại.");
      await response.json();
      for (;;) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        const jobResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001"}/videos/${video.id}/job`);
        if (!jobResponse.ok) throw new Error((await jobResponse.text()) || "Không thể đọc trạng thái pipeline.");
        const job = (await jobResponse.json()) as ProcessingJob | null;
        if (!job) throw new Error("Không tìm thấy processing job.");
        setNotice(`Đang xử lý: ${job.currentStep ?? "QUEUED"} (${job.progress}%)`);
        if (job.status === "FAILED") throw new Error(job.errorMessage || "Pipeline thất bại.");
        if (job.status === "COMPLETED") break;
      }

      const processedResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001"}/videos/${video.id}`);
      if (!processedResponse.ok) throw new Error("Không thể tải kết quả pipeline.");
      const processed = (await processedResponse.json()) as Video;
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

  async function importTranscript(file: File) {
    if (!video) {
      setNotice("Hãy tạo video YouTube trước khi import transcript.");
      return;
    }
    setLoading(true);
    setNotice(`Đang import ${file.name}...`);
    try {
      const payload = JSON.parse(await file.text()) as unknown;
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001"}/videos/${video.id}/transcript-import`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error((await response.text()) || "Import transcript thất bại.");
      await response.json();
      for (;;) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const jobResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001"}/videos/${video.id}/job`);
        if (!jobResponse.ok) throw new Error((await jobResponse.text()) || "Không thể đọc trạng thái import.");
        const job = (await jobResponse.json()) as ProcessingJob | null;
        if (!job) throw new Error("Không tìm thấy processing job.");
        setNotice(`Đang import: ${job.currentStep ?? "QUEUED"} (${job.progress}%)`);
        if (job.status === "FAILED") throw new Error(job.errorMessage || "Import transcript thất bại.");
        if (job.status === "COMPLETED") break;
      }
      const processedResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001"}/videos/${video.id}`);
      if (!processedResponse.ok) throw new Error("Không thể tải segments sau import.");
      const processed = (await processedResponse.json()) as Video;
      const mapped = (processed.segments ?? []).map((segment) => ({ ...segment, id: segment.order ?? segment.id }));
      setVideo(processed);
      setSegments(mapped);
      setSelectedId(mapped[0]?.id ?? 0);
      setNotice(`Đã import và tạo ${mapped.length} câu transcript.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Import transcript thất bại.");
    } finally {
      setLoading(false);
    }
  }

  async function saveDraft() {
    if (!video) {
      setNotice(`Đã lưu bản nháp gồm ${segments.length} câu.`);
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001"}/videos/${video.id}/segments`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ segments }),
      });
      if (!response.ok) throw new Error((await response.text()) || "Không thể lưu segments.");
      setNotice(`Đã lưu ${segments.length} câu vào database.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Không thể lưu bản nháp.");
    } finally {
      setLoading(false);
    }
  }

  async function exportJson() {
    if (!video) {
      setNotice("Hãy tạo video trước khi export.");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001"}/videos/${video.id}/export`, { method: "POST" });
      if (!response.ok) throw new Error((await response.text()) || "Export thất bại.");
      const payload = await response.json();
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
      const downloadUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = `${video.youtubeId ?? video.id}-learning.json`;
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(downloadUrl);
      setNotice("Đã export JSON.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Không thể export JSON.");
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
          <div className="actions">
            <button className="ghost" onClick={() => transcriptInput?.click()} disabled={!video}>Import transcript.json</button>
            <button className="primary" onClick={processVideo} disabled={loading}>{loading ? "Đang chạy..." : "Chạy pipeline"}</button>
            <input
              ref={setTranscriptInput}
              type="file"
              accept="application/json,.json"
              hidden
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void importTranscript(file);
                event.target.value = "";
              }}
            />
          </div>
        </section>
      )}

      <div className="workspace">
        <section className="panel player-panel">
          <div className="panel-heading">
            <div><span className="eyebrow">VIDEO</span><h2>Playback</h2></div>
            <span className="count">{activeSegmentId ? `Câu ${activeSegmentId}` : "Chưa phát"}</span>
          </div>
          {video?.youtubeId ? <div className="player-frame" ref={playerElementRef} /> : <p className="empty">Tạo video YouTube để hiển thị player.</p>}
        </section>
        <section className="panel transcript-panel">
          <div className="panel-heading">
            <div><span className="eyebrow">TRANSCRIPT</span><h2>Chinese Conversation</h2></div>
            <span className="count">{segments.length} câu</span>
          </div>
          <div className="segment-list">
            {segments.map((segment) => (
              <button className={`segment-row ${segment.id === selectedId ? "selected" : ""} ${segment.id === activeSegmentId ? "playing" : ""}`} key={segment.id} onClick={() => seekToSegment(segment)}>
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
              <div className="actions"><button className="ghost" onClick={exportJson} disabled={loading}>Export JSON</button><button className="primary" onClick={saveDraft} disabled={loading}>Lưu bản nháp</button></div>
            </div>
          ) : <p className="empty">Chọn một câu để bắt đầu chỉnh sửa.</p>}
        </section>
      </div>
      <p className="notice" role="status">{notice}</p>
    </main>
  );
}
