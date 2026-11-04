---
name: smoke-check
description: Bring up the full ViTube stack and run the end-to-end scenario (register, upload, watch, like, comment, private access). Use before declaring a stage done.
---

# Smoke check

1. `docker compose up -d --build --wait`. If a service is unhealthy, check `docker compose logs <service>`.
2. `curl -fsS http://localhost/api/health` and `curl -fsS http://localhost/docs` must return 200.
3. Run the e2e scenario: `docker compose -f compose.test.yml run --rm e2e`. It runs `tests/e2e/test_scenario.py` against
   the running stack.
4. Expected flow:
    - register → upload a small generated video → poll until `READY` → feed and search → GET the media URL with Range (
      206) → like → comment;
    - a stranger gets 404 on a private video and on its media URL;
    - after access is granted, the stranger can watch.
5. Report pass/fail per step with the failing response body. Don't change code during the check.
