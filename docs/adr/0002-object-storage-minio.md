# 0002. Video storage: MinIO behind nginx

**Status:** accepted · 2026-11-04

**Context.** Videos are hundreds of MB. Storing them as DB blobs bloats the database and breaks seeking.

**Decision.**

- PostgreSQL keeps metadata only. Object keys are built from ids (below), so they aren't stored.
- Bytes live in MinIO (self-hosted, S3-compatible), with a Docker volume.
- api and worker log in as MinIO user `vitube-app`: objects in the bucket only, no admin API or bucket policies
  (like `vitube_app` in Postgres, [0010](0010-db-roles.md)). Uploads go in parts and are aborted on any error.
- MinIO is not exposed. Browsers reach it only via nginx `/media/*` after an access
  check ([0004](0004-media-access-auth-request.md)).
- One bucket `vitube`. Keys are built from UUIDs, never from user file names:
  `originals/{video_uuid}`, `videos/{video_uuid}/720p.mp4`, `thumbs/{video_uuid}.jpg`, `avatars/{user_uuid}.jpg`,
  `banners/{user_uuid}.jpg`.
- Image: `pgsty/minio`, a community build of MinIO, pinned by tag. MinIO Inc. stopped publishing free images in 2025 (
  `minio/minio` is gone).

**Alternatives.** Local disk + nginx `X-Accel-Redirect`: fewer parts, but tied to one host and no real storage layer.

**Consequences.**

- ➕ Switching to AWS S3 is a config change.
- ➖ One more service, plus a one-shot container to create the bucket.
- ➖ The image comes from a community maintainer. If it stalls, any S3-compatible server works (the app only uses the S3
  API).
