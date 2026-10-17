# Agent audit dashboard

React 19 and TypeScript client, served on the audit hub's origin. All fonts are bundled locally. There are no fallback datasets or browser-stored access tokens.

Use Node 22.16 or newer supported by Vite 8:

```sh
cd dashboard
npm ci
npm run build
```

The build runs the TypeScript checker and writes `dashboard/dist`. Configure the hub's `AEK_STATIC_DIR` to its absolute path. For local UI development run `npm run dev`; Vite forwards `/api` to `http://127.0.0.1:8787`. Configure `AEK_PUBLIC_ORIGIN` to the browser origin (`http://127.0.0.1:5173` for Vite) and explicitly allow insecure loopback cookies for local development only. Production uses HTTPS and secure cookies.

Sign in with an operator-provisioned viewer or reviewer key. A browser session is established by the server; every browser mutation sends the session's CSRF token. Viewers can inspect records. Reviewers can append a disposition with a note. Sign out revokes the browser session.

Receipt activity, active-agent counts, reported run state and artifact hashes are labeled according to their actual meaning. The interface never claims heartbeat-backed availability or central artifact verification. Synthetic organizations display a demo badge.

Use **Refresh data** in the workspace header to reload the currently visible API views. Refresh is explicit rather than periodic, so background network activity does not interrupt review drafts. A successful review submission refreshes that run and its review history.
