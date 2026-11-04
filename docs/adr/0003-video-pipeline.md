# 0003. Processing: Celery + ffmpeg, MP4 first, HLS later

**Status:** accepted · 2026-11-04

**Context.** Users upload any format (HEVC `.mov`, `.avi`, 4K). Browsers reliably play only MP4 (H.264 + AAC).
Transcoding takes minutes, so it can't run inside an HTTP request.

**Decision.**

- API stores the original, sets `PROCESSING`, and queues a Celery task (Redis broker).
- A separate `worker` container with ffmpeg runs it:
  `ffprobe` (is it a video? duration within limit?) → `ffmpeg` to MP4 H.264/AAC with `+faststart`, height ≤ 720 →
  thumbnail → upload to MinIO → `READY`.
- Errors set `FAILED` with a readable `error_message`.
- States: `UPLOADING → PROCESSING → READY | FAILED`.
- Playback: progressive MP4 via HTTP Range (206), so seeking works.
- HLS (several qualities, quality switch) is a later stage. Only worker commands and the player change.

**Alternatives.** HLS from day one: closer to YouTube, but 2–3× slower transcoding, many files per video, harder access
checks.

**Consequences.**

- ➕ Simple, reliable core flow.
- ➖ No quality switch until the HLS stage.
