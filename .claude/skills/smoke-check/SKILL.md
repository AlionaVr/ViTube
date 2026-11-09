---
name: smoke-check
description: Bring up the full ViTube stack and run the end-to-end scenario (register, upload, watch, like, comment, private access). Use before declaring a stage done.
---

# Smoke check

1. `docker compose up -d --build --wait`. If a service is unhealthy, check `docker compose logs <service>`.
2. `curl -fsS http://localhost/api/health` and `curl -fsS http://localhost/docs` must return 200.
3. Run the e2e scenario from `backend/`: `E2E_BASE_URL=http://localhost uv run pytest tests/e2e -v` (needs ffmpeg).
   It runs `tests/e2e/test_scenario.py` against the running stack, through nginx.
4. Expected flow (feed, search, like and comment join as their stages land):
    - sign in → upload a small generated video → poll until `READY` → GET the media URL with Range (206), 720p;
    - private: a guest gets 404 on the page and 401 on the media URL, a stranger 404 on both;
    - after access is granted, the stranger can watch; after it is taken back, 404 again at once;
    - public: a guest can watch; a file that is not a video ends `FAILED` with a reason.
5. Report pass/fail per step with the failing response body. Don't change code during the check.
