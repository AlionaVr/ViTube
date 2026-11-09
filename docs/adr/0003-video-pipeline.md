# 0003. Processing: Celery + ffmpeg, MP4 first, HLS later

**Status:** accepted · 2026-11-04

**Context.** Users upload any format (HEVC `.mov`, `.avi`, 4K). Browsers reliably play only MP4 (H.264 + AAC).
Transcoding takes minutes, so it can't run inside an HTTP request.

**Decision.**

- API stores the original, sets `UPLOADED`, and queues a Celery task (Redis broker).
- A separate `worker` container with ffmpeg runs it:
  - claims the video: `UPLOADED → PROCESSING` in one conditional `UPDATE`, so a duplicate task does nothing;
  - `ffprobe` (is it a video? duration within limit?) → `ffmpeg` to MP4 H.264/AAC with `+faststart`, height ≤ 720 →
    thumbnail → upload to MinIO → `READY`.
  - ffmpeg reads uploads with lists of allowed container formats and decoders, local files only and a pixel cap
    (8K) on every frame, so a playlist posing as a video can't fetch URLs or read other files. It runs with no
    secrets in its environment. Output drops metadata (phone GPS tags). Work files go to a volume, cleared when the
    worker starts. The worker has a memory limit and a low CPU share.
  - One deadline for the whole job (2 h), shorter than the sweeper's lease (3 h); Celery kills a job that hangs
    past it. No DB transaction stays open while ffmpeg runs.
- A bad file sets `FAILED` with a readable `error_message`. Other errors (storage, DB, a lost worker) put the video
  back to `UPLOADED`: the stored original is processed again, never uploaded again.
- A sweeper (Celery beat) re-queues videos stuck in `UPLOADED` and takes back `PROCESSING` jobs older than the task
  time limit. After 3 attempts the video is `FAILED`. A DB trigger stamps `status_changed_at` on every change.
- States: `UPLOADING → UPLOADED → PROCESSING → READY | FAILED`. *(Amended 2026-11-07: `UPLOADED`, claim and
  sweeper added, so a broker or worker failure doesn't cost a new upload.)*
- Playback: progressive MP4 via HTTP Range (206), so seeking works.
- HLS (several qualities, quality switch) is a later stage. Only worker commands and the player change.

**Alternatives.** HLS from day one: closer to YouTube, but 2–3× slower transcoding, many files per video, harder access
checks.

**Consequences.**

- ➕ Simple, reliable core flow.
- ➖ No quality switch until the HLS stage.
