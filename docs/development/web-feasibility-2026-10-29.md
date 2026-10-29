# Browser version feasibility — 29 October 2026

A browser version is feasible. The current desktop package cannot simply be
uploaded as a website. No browser build has been implemented or benchmarked in
this update; the estimates below are engineering judgments based on the code
and current runtime documentation, not delivery commitments.

## What can be reused

- The 47 verified lessons, 16 published courses, recorded moves, hints, reviewed
  answer branches, character stories and portraits.
- Pure Python board representation, legal moves, notation, search, lesson and
  replay controllers. These are largely independent of Pygame.
- The rules for help tracking, revisioned progress, challenge unlocks and medals.
  Preserve their contracts and regression cases through any storage change.

The main presentation layer is substantial: `ui.py` is about 3,400 lines and
`menu.py` about 1,000. The browser work is primarily runtime integration,
presentation and persistence rather than writing chess lessons again.

## Options

| Approach | Reuse | Main work | Best fit |
| --- | --- | --- | --- |
| Pygbag / pygame-ce in WebAssembly | Most existing drawing and Python | Async loop, startup/search adapters, durable browser storage, fonts/assets, downloads, audio and viewport behavior | Fastest experiment with the existing desktop experience |
| HTML/CSS/TypeScript UI with Python in a Pyodide worker | Content and Python chess/lesson logic | New interface, message protocol, browser persistence and engine worker lifecycle | Longer-term responsive website, particularly phones and accessible controls |
| Web UI with a Python server | Python domain code | New interface, API/session isolation, hosting, concurrency limits and server-side search capacity | Later if accounts, shared progress or managed analysis are required |

Recommendation: first run a bounded Pygbag compatibility spike. If loading,
search responsiveness and persistence meet the acceptance checks below, use it
for an initial desktop/laptop tester beta. If reaching phones is essential from
the first release, prefer the HTML interface with a Pyodide worker; a canvas
port retains the desktop UI's limitations. Both client-side approaches can be
served as static assets, so additional testers need download bandwidth rather
than a server running one chess engine per player. No account system is needed
for the first beta.

## Concrete blockers in this checkout

1. `ChessUI.run()` and `run_startup_task()` use synchronous loops. Pygbag
   requires an async-aware loop that yields to the browser each iteration.
   Split initialization and frame processing from the desktop runner.
2. Startup and AI launch Python threads. Do not assume these work in browser
   runtimes. Pyodide documents `threading` as nonfunctional. Run engine work
   in a Web Worker, or prove a supported cooperative search alternative in the
   Pygbag spike. Cancellation must preserve the current session/FEN safeguards;
   reset or replace a busy worker rather than accepting an obsolete result.
3. Progress and challenge recovery use SQLite at an XDG filesystem location.
   A browser's in-memory filesystem is not durable storage. Prove a supported
   SQLite/IndexedDB filesystem integration in the chosen runtime, or implement
   a persistence adapter with the same atomic update and migration contracts.
   Pyodide's IDBFS requires explicit asynchronous synchronization. The SQLite
   JavaScript OPFS APIs are a separate integration, not a drop-in replacement
   for Python's `sqlite3`. Test reload, tab close, quota/storage denial and two
   tabs. Local browser progress does not follow a tester between devices and
   can be removed by clearing site data; provide export/import.
4. Themes probe host files and execute desktop commands; use the built-in
   palette on the web. Bundle a licensed UI/chess font or piece sprites rather
   than relying on Linux fonts. Pygbag uses pygame-ce; this checkout currently
   runs Pygame 2.6.1, so verify API and rendering compatibility.
5. The seven BMP portraits total roughly 2 MiB uncompressed. Package compressed
   portraits, avoid shipping desktop-only files, and measure cold/warm loading
   on an ordinary connection. A Python/WASM runtime adds download/startup cost;
   there is no measured browser payload yet.
6. PGN load/save and recovery export currently use filesystem paths. Replace
   these with browser uploads/downloads and useful success/error messages.
   Audio needs an explicit user gesture and a silent fallback.
7. The desktop minimum is 360×720 or 720×600. Phone browser chrome, rotation,
   browser zoom and virtual keyboards need a separate layout strategy. Test
   taps, pointer cancellation and dragging without scrolling the whole page.
8. A browser refresh or navigation can interrupt progress writes. Persist at
   meaningful actions, not only in an unload handler. Include content/build
   versions in downloadable bug reports without collecting personal data.

## Smallest useful tester release

Start with one URL, a clear loading screen, Chicky's first course, free local
play, one AI opponent, saved lesson progress, and a feedback route that includes
an optional build identifier. Then enable all lessons, challenges, medals and
review once storage and cancellation are verified. Keep badges local and
private. Add a visible reset/export control for testers sharing a browser.

Acceptance checks before sharing the beta:

- Cold load, first move and first AI reply measured in Chromium, Firefox and
  Safari; include at least one slower laptop and actual phones if advertised.
- Browser remains responsive during startup and a six-second Monty search;
  leaving/restarting a match cannot apply the previous worker's answer.
- Castling, en passant, promotion picker, check/mate, replay, hints, independent
  answers, reload/resume and entitlement rules agree with desktop cases.
- Saved progress survives a real reload and browser restart; storage errors
  remain actionable. Separate tabs cannot silently overwrite challenge state.
- Keyboard, mouse and touch navigation; long questions; every text size;
  portrait/landscape resize; focus after closing dialogs; sound off/on.
- Release assets and content versions update together, and rollback is possible.

A short compatibility spike is roughly **1–3 focused engineering days**. A
usable Pygbag tester beta is plausibly **1–3 weeks after a successful spike**.
A browser-native interface with Python workers is more likely **4–8 weeks**
for a broad beta with the existing feature set. Browser/device failures or a
new persistence design can extend either estimate. Start with the spike rather
than promising a full port on those dates.

## Sources checked

- [Pygame web / Pygbag requirements](https://pygame-web.github.io/): async loop,
  supported packaging conventions and compressed assets.
- [Pygbag source and documentation](https://github.com/pygame-web/pygbag).
- [Pyodide Python compatibility](https://pyodide.org/en/stable/usage/wasm-constraints.html):
  threading and platform constraints.
- [Pyodide workers](https://pyodide.org/en/stable/usage/webworker.html): run Python
  computation away from the browser UI through message passing.
- [Pyodide FAQ](https://github.com/pyodide/pyodide/blob/main/docs/usage/faq.md):
  explicitly synchronize IDBFS for persistence.
- [SQLite WASM persistence](https://www.sqlite.org/wasm/doc/trunk/persistence.md):
  storage/worker alternatives and concurrent-tab limitations.
