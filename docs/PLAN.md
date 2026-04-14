# Project Plan

This plan expands the work into clear checklists with tests and success criteria. Each part ends with a user approval gate before moving on.

## Part 1: Plan

Checklist
- [ ] Expand this document with detailed steps, tests, and success criteria for Parts 1-10
- [ ] Create frontend/AGENTS.md describing the existing frontend codebase and test setup
- [ ] User reviews and approves the plan

Tests
- None (documentation-only)

Success criteria
- docs/PLAN.md fully describes steps, tests, and success criteria for each part
- frontend/AGENTS.md exists and accurately summarizes the current frontend
- User approval recorded before work continues

## Part 2: Scaffolding

Checklist
- [ ] Add Dockerfile and docker-compose setup to run frontend build + FastAPI backend in one container
- [ ] Create backend/ FastAPI app with a health route and a sample API route
- [ ] Serve a simple static HTML page from FastAPI at / that calls the sample API route
- [ ] Add start/stop scripts for Mac, Windows, Linux under scripts/
- [ ] Document how to run the container locally in a minimal README section
- [ ] User reviews and approves scaffold behavior

Tests
- Manual: run container, open / and confirm page renders and API call succeeds
- Manual: verify sample API route returns expected JSON

Success criteria
- Container starts via scripts and serves HTML at /
- HTML makes a working call to the sample API route
- Backend responds with expected JSON and status codes

## Part 3: Add in Frontend

Checklist
- [ ] Configure build so Next.js frontend is statically built and served by FastAPI
- [ ] Ensure / shows the existing Kanban demo UI
- [ ] Update any routing or asset paths needed for static hosting
- [ ] Add Vitest unit and integration tests for core UI and state behavior
- [ ] User reviews and approves UI served from backend

Tests
- Automated: `npm run test:unit` in frontend
- Manual: load / in container and verify Kanban UI renders

Success criteria
- Static frontend build is served at /
- Kanban board renders with existing behavior
- Vitest tests pass

## Part 4: Fake User Sign-In

Checklist
- [ ] Add login screen gating the Kanban at /
- [ ] Accept only "user" / "password" and enable logout
- [ ] Store session state in a simple, local mechanism
- [ ] Update frontend tests for auth flow (Vitest)
- [ ] User reviews and approves login UX

Tests
- Automated: `npm run test:unit` in frontend
- Manual: login with valid credentials, reject invalid, logout returns to login screen

Success criteria
- Unauthenticated users see login screen
- Valid credentials show Kanban
- Logout returns to login screen
- Vitest tests pass

## Part 5: Database Modeling

Checklist
- [ ] Propose Kanban database schema for multi-user support
- [ ] Save schema JSON to ./schemas/myschema.json
- [ ] Add a short docs note explaining tables and relationships
- [ ] User reviews and approves schema

Tests
- None (design-only)

Success criteria
- schemas/myschema.json exists and matches proposed schema
- docs update explains schema decisions
- User approval recorded

## Part 6: Backend API

Checklist
- [ ] Implement SQLite-backed data layer for users, board, columns, cards
- [ ] Add FastAPI routes to read and update Kanban data per user
- [ ] Ensure database is created if missing
- [ ] Add backend unit tests for routes and data behavior
- [ ] User reviews and approves API behavior

Tests
- Automated: backend unit tests (pytest)
- Manual: verify API with sample requests

Success criteria
- API supports read and write for Kanban
- SQLite DB is created on first run
- Tests pass

## Part 7: Frontend + Backend Integration

Checklist
- [ ] Update frontend to use backend API for data
- [ ] Ensure UI reflects persisted data changes
- [ ] Add Vitest integration tests for API-backed behavior
- [ ] User reviews and approves end-to-end flow

Tests
- Automated: `npm run test:unit` in frontend
- Manual: create/rename/move cards and confirm persistence

Success criteria
- UI reads from and writes to backend
- Changes persist across reloads
- Vitest tests pass

## Part 8: AI Connectivity

Checklist
- [ ] Add backend OpenRouter client using OPENROUTER_API_KEY
- [ ] Implement a simple "2+2" API test route for AI connectivity
- [ ] Add backend tests or manual validation steps
- [ ] User reviews and approves connectivity

Tests
- Manual: call AI test route and confirm response contains "4"

Success criteria
- Backend successfully calls OpenRouter and returns response

## Part 9: AI Structured Outputs

Checklist
- [ ] Propose Structured Outputs JSON schema for AI responses
- [ ] Update AI call to include board JSON + user message + history
- [ ] Validate AI responses against the schema
- [ ] Add backend tests for schema validation and optional board updates
- [ ] User reviews and approves schema and behavior

Tests
- Automated: backend unit tests for schema parsing
- Manual: send a prompt that should update the board and verify response

Success criteria
- AI responses conform to schema
- Optional Kanban updates apply correctly
- Tests pass

## Part 10: AI Chat Sidebar UI

Checklist
- [ ] Add sidebar UI for chat history and input
- [ ] Wire UI to backend AI endpoint
- [ ] Apply Kanban updates from AI responses and refresh UI
- [ ] Add Vitest tests for chat UI behavior
- [ ] User reviews and approves final experience

Tests
- Automated: `npm run test:unit` in frontend
- Manual: chat, receive response, and verify board updates

Success criteria
- Chat sidebar works end-to-end
- Kanban updates apply automatically
- Vitest tests pass