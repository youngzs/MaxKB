# finance — 融资工作台 (Finance Workspace)

Backend Django app for the MaxKB Finance Workspace module. Provides the API surface for fund-raising document workflows: template management, draft preparation, multi-stage review, and dispatch. Gate 1 ships only the app scaffold and a public health-check endpoint at `GET /api/finance/ping`; models, serializers, and business logic are introduced in subsequent gates. Web-only — not registered in the `local_model` settings profile.
