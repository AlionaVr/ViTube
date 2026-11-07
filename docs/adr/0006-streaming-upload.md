# 0006. Upload: streamed through the API, layered limits

**Status:** accepted · 2026-11-04

**Context.** Upload needs file selection, progress and metadata. Without limits one user can fill the disk or CPU (DoS).

**Decision.**

- A draft first: `POST /api/videos` with the metadata. Then the file alone: `PUT /api/videos/{id}/file`, the raw
  request body. *(Amended 2026-11-07: was one multipart request. Raw body needs no multipart parser, and the draft
  lets metadata be edited during the upload.)*
- The API streams the body to MinIO in 8 MiB parts (S3 multipart upload) and never holds the whole file in memory.
  nginx: `proxy_request_buffering off`.
- Only the owner uploads, one upload per video at a time (a Redis lock); CSRF checks as for any unsafe request.
- A cut-off or refused upload is aborted: nothing is stored, the video stays `UPLOADING`, the client can retry.
  Processing is queued only after the file is stored and `UPLOADED` is committed.
- Progress comes from `XMLHttpRequest.upload.onprogress`.
- Metadata can be edited at any time (`PATCH`), independent of the upload.
- Limits (in `.env`, documented in README):

  | Variable | Default |
    |---|---|
  | `MAX_UPLOAD_SIZE_MB` | 1024 |
  | `MAX_VIDEO_DURATION_SEC` | 1800 |
  | `MAX_VIDEO_HEIGHT` | 720 (taller videos are downscaled) |

- Checked in layers:
    1. frontend `file.size` (UX only);
    2. nginx `client_max_body_size` (413), from the same `MAX_UPLOAD_SIZE_MB`;
    3. API counts real bytes; `Content-Length` only refuses early;
    4. worker `ffprobe`.

**Alternatives.**

- Chunked upload with resume: planned as an extra stage.
- Direct presigned upload to MinIO: most complex; checks spread across services.

**Consequences.**

- ➕ Simple code, all checks in one place.
- ➖ A dropped connection restarts the upload (fixed by the chunked stage).
