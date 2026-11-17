# Dashboard data missing on first open (needs a manual refresh)

## Symptom
Opening the site after a while away shows an empty dashboard (My Deals 0,
Bought Deals 0, no portfolio bar). One refresh fixes it, and reopening soon
after also works.

## Root cause
A race between two things that start at the same moment on page load:

1. `App.vue` `onMounted` calls `dealStore.fetchDeals()` right away.
2. The router guard (`router/index.ts`) calls `authStore.load()`, which reads
   `/auth/config` and refreshes an expired session.

The access cookie lives 15 minutes (`AUTH_ACCESS_MINUTES`, default 15). After a
longer gap the browser has dropped it, so `GET /deals` answers 401. The 401
interceptor in `api/index.ts` only refreshes when `auth.enforced` is true, but
`auth.config` has not loaded yet at that instant, so `enforced` reads `false`:
no refresh, no retry, `fetchDeals` fails quietly and the store stays `[]`.
Meanwhile `auth.load()` refreshes the session successfully, so the page looks
connected but empty. On a refresh the cookie is fresh, so it works; within 15
minutes reopening also works.

## Fix (minimal)
- [x] In `App.vue`, wait for the first navigation (`await router.isReady()`,
      i.e. after the guard's `auth.load()` has refreshed the session) before
      `fetchDeals()`, and skip it when the session ended up `anon`/`pending`
      (the user is on the login page). (~10 min)
- [x] In the 401 interceptor (`api/index.ts`), when the auth status is still
      `unknown`, await `auth.load()` before reading `auth.enforced`, so any
      other early request also refreshes instead of failing silently. (~15 min)

## Tests
- [x] Unit (Vitest): 401 interceptor — with auth status `unknown`, a 401 on a
      data route triggers `load()` and then a single retry that succeeds. (~20 min)
- [x] Unit (Vitest): `App.vue` — `fetchDeals` runs only after the router is
      ready, and not when the status is `anon`. (~20 min)
- [x] Integration: none needed in the backend (no backend change); existing
      Vitest suite and `vue-tsc` build must stay green. (~5 min)
- [x] E2E (Playwright): page load where the first `GET /active-deals` answers 401
      until `/auth/refresh` has been called; the dashboard shows the deal
      count without a reload. (~30 min)

## MCP server support
- N/A: no new feature or endpoint; frontend load-order bug fix only.

## Done notes
- The session renewal is shared: `authStore.load()` now returns the in-flight
  call to anyone who asks while it runs. The API treats a second
  `/auth/refresh` with the same token as a replay and revokes the whole
  session family (`BL/auth/session.py`), so the 401 handler waits on that one
  load instead of starting its own refresh.
- `App.vue` also covers the visitor who had to sign in first: the deals load
  once, the moment the status becomes `trusted` (or `off`).
- Unit tests: `src/App.dealsFetchWaitsForSession.test.ts`,
  `src/api/expiredSessionOnPageLoad.test.ts`, one new case in
  `src/stores/authStore.test.ts`. E2E: `e2e/flows/landing-expired-session.spec.ts`.
  All of them fail on the previous code (the E2E one with "My Deals 0").

## Security task
Contents of `.claude/security.md`:
> Please check through all the code you just wrote and make sure it follows
> security best practices. make sure there are no sensitive information in the
> frontend and there are no vulnerabilities that can be exploited throughout
> all the code in this repo

- [x] Review the change: no token/cookie values logged or stored in JS, the
      refresh still happens at most once per wave (shared `refreshing`
      promise), no retry loop on a failed refresh, public inspection routes
      still never trigger a login redirect. (~10 min)

## Finish
- [ ] Push the branch and open a PR. (~5 min)
