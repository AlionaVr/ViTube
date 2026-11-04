# Architecture Decision Records

One short file per key decision: context, decision, alternatives, consequences.

| #                                         | Decision                                          |
|-------------------------------------------|---------------------------------------------------|
| [0001](0001-frontend-spa.md)              | Frontend: React + TypeScript + Vite SPA           |
| [0002](0002-object-storage-minio.md)      | Video storage: MinIO behind nginx                 |
| [0003](0003-video-pipeline.md)            | Processing: Celery + ffmpeg, MP4 first, HLS later |
| [0004](0004-media-access-auth-request.md) | Media access: nginx `auth_request`                |
| [0005](0005-server-sessions.md)           | Auth: server-side sessions in Redis + CSRF        |
| [0006](0006-streaming-upload.md)          | Upload: streamed through the API, layered limits  |
| [0007](0007-search-postgres-fts.md)       | Search: PostgreSQL FTS + pg_trgm                  |
| [0008](0008-deployment.md)                | Deploy: `install.sh` + Docker Compose             |
| [0009](0009-moderation-audit.md)          | Moderation: reports, hiding, audit log            |
