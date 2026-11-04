# 0006. Upload: streamed through the API, layered limits

**Status:** accepted · 2026-11-04

**Context.** Upload needs file selection, progress and metadata. Without limits one user can fill the disk or CPU (DoS).

**Decision.**

- One multipart request to the API. The API streams it to MinIO in chunks and never holds the whole file in memory.
  nginx: `proxy_request_buffering off`.
- Progress comes from `XMLHttpRequest.upload.onprogress`.
- Metadata can be edited while uploading and processing.
- Limits (in `.env`, documented in README):

  | Variable | Default |
    |---|---|
  | `MAX_UPLOAD_SIZE_MB` | 1024 |
  | `MAX_VIDEO_DURATION_SEC` | 1800 |
  | `MAX_VIDEO_HEIGHT` | 720 (taller videos are downscaled) |

- Checked in layers:
    1. frontend `file.size` (UX only);
    2. nginx `client_max_body_size` (413);
    3. API counts real bytes and ignores `Content-Length`;
    4. worker `ffprobe`.

**Alternatives.**

- Chunked upload with resume: planned as an extra stage.
- Direct presigned upload to MinIO: most complex; checks spread across services.

**Consequences.**

- ➕ Simple code, all checks in one place.
- ➖ A dropped connection restarts the upload (fixed by the chunked stage).
