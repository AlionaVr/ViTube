---
name: add-endpoint
description: Add a new FastAPI endpoint to ViTube following the module layering (schema, repository, service, router, test). Use when adding or changing an API route.
---

# Add an endpoint

Work inside `backend/app/modules/<domain>/`.

1. **Schemas** (`schemas.py`): request model with explicit fields and limits (`Field(max_length=...)`); response model.
   Never expose ORM objects.
2. **Repository** (`repository.py`): queries only. Parameterized SQLAlchemy, no business rules.
3. **Service** (`service.py`): business rules and access checks. Use `can_view` for videos. Raise domain errors (
   `NotFound`, `Forbidden`), not HTTP ones.
4. **Router** (`router.py`):
    - thin layer;
    - deps: `current_user` / `optional_user` / `require_role(...)`; unsafe methods get CSRF via the router dependency;
    - `response_model`, `summary` and `tags` for Swagger.
5. **Register** the router in `app/main.py` if the module is new.
6. **Tests** (`backend/tests/<domain>/`): happy path, 401, wrong user, 422. Use the `test-writer` agent for bigger
   changes.
7. **Frontend types:** run `npm run gen:api` in `frontend/` so TS types match.
8. **Check:** run ruff, pyright and pytest.
