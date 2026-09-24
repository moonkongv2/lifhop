# lifhop Capture Strategy

This document defines the product and architecture direction for getting user data into lifhop with as little repeated effort as practical.

It complements `ROADMAP.md` and `DECISIONS.md`.

The capture strategy is intentionally provider-aware. Different external services expose different APIs, browser surfaces, mobile sharing behavior, export mechanisms, and policy constraints. lifhop should not force every provider through one acquisition mechanism.

---

# Product Principle

The long-term product should not depend on users repeatedly performing:

```text
Request export
    |
    v
Wait for export
    |
    v
Download archive
    |
    v
Open lifhop
    |
    v
Upload archive
```

That workflow remains useful for historical recovery and migration, but it is too much repeated effort to be the primary ongoing capture experience.

The guiding principle is:

> Use zero-effort capture where a stable and permitted integration exists, and the lowest practical user effort where it does not.

Conceptually:

```text
0 effort
- OAuth/API continuous sync
- webhook-based sync
- native MCP / hook / plugin capture
- opt-in browser auto-capture where technically and policy-wise acceptable

1 action
- mobile Share -> lifhop
- browser Save to lifhop

higher effort
- export / download / upload
- reserved mainly for historical enrichment
```

The product should provide value from data captured from now onward without requiring a complete historical archive before the user can begin.

---

# Capture vs Ingestion

How lifhop obtains data should remain separate from how lifhop understands and stores it.

```text
Capture / Acquisition
        |
        v
Provider raw data
        |
        v
Provider Parser / Adapter
        |
        v
Canonical Item
        |
        v
Entry Normalizer
        |
        v
Entry
```

Possible capture clients include:

```text
Capture Client
├── Chromium Extension
├── iOS Share Extension
├── Android Share Target
├── OAuth / API Connector
├── MCP / CLI Hook / Plugin
├── Local Folder Watcher
└── Email Forwarding
```

The downstream importer / canonical / normalization boundaries introduced in Steps 4–6 should be reused rather than creating a separate persistence path for each capture mechanism.

Historical ZIP import is therefore one acquisition mechanism, not the architectural center of lifhop.

---

# Capture Modes

The following conceptual modes should guide later implementation. Exact enum names and persistent schema are intentionally deferred until the productization step.

```text
HISTORICAL_IMPORT
- user-provided exports / archives
- primarily historical enrichment

BROWSER_CAPTURE
- browser extension
- user-initiated or opt-in continuous capture

MOBILE_SHARE
- iOS Share Extension / Android Share Target
- user explicitly shares supported content to lifhop

CONNECTED_SYNC
- OAuth/API/webhook/polling
- initial sync + incremental sync

NATIVE_CAPTURE
- MCP, agent plugin, CLI hook, SDK, or event hook
- capture at the source application boundary

LOCAL_CAPTURE
- watched folders / local documents
- future desktop-oriented option
```

---

# 1. Browser Continuous Capture

## Initial target

The first PoC should target ChatGPT Web using a Chromium extension.

The PoC exists to validate whether low-effort conversation capture is technically useful before lifhop commits to a production browser integration.

Initial progression:

```text
v0
ChatGPT Web
    |
    v
[Save to lifhop]
    |
    v
capture current conversation
    |
    v
existing ingestion pipeline

v0.x
conversation changes
    |
    v
extension detects update
    |
    v
user can save updated state

PoC extension
opt-in Auto Capture
    |
    v
new/changed conversation state
    |
    v
capture after debounce / completion boundary
```

The first PoC should remain intentionally small. It does not need Chrome Web Store publication, polished UI, multi-provider support, or a production-grade connection model.

## Verified manual PoC — 2026-09-25

The manual ChatGPT Web flow has been implemented and verified locally:

```text
User clicks Save to lifhop
    |
    v
Extension scrolls through the active conversation,
collects user/assistant turns, and reconstructs Markdown
    |
    v
Capture diagnostics check the scan's endpoints and count
    |
    v
JWT-authenticated POST /captures/chatgpt
    |
    v
ConversationPayload -> EntryNormalizer
    |
    v
upsert_external_entry() -> PostgreSQL
```

The ZIP import worker and Capture API reuse the same external Entry upsert service. The service does not commit; the caller owns the transaction. A second capture of the same ChatGPT conversation updates the same Entry instead of creating a duplicate.

Manual change detection is also verified. The extension computes a SHA-256 fingerprint over conversation title, message IDs, roles, and content; the previous successful fingerprint, count, Entry ID, and save time live in `chrome.storage.local`, scoped by API URL, user ID, and conversation ID. An unchanged manual capture skips the API request. The local cache stores no duplicate conversation transcript and is not authoritative server state. A server-side update or ZIP import can make it stale.

Current safeguards: request validation checks the top/bottom scroll flags, reported message count, and first-message role. These checks catch some obvious failures but cannot prove complete capture under DOM virtualization. The current full-replacement upsert does not protect a fuller Entry from a later incomplete or stale snapshot.

Observed extractor limitations include citation UI text in some answers, excess blank lines, incomplete code-language metadata, and no structured persistence yet for per-message IDs or source URLs. Browser coverage does not include mobile-app conversations. This PoC does not settle production terms/policy acceptability.

## Next experiment — opt-in change observation

The next Step 6.5 experiment is deliberately **notification-only**:

- A content script observes DOM changes with `MutationObserver` only after explicit opt-in.
- After a quiet/debounce window, it notifies an extension service worker even when the popup is closed.
- Verify that scrolling/virtualization, navigation, response streaming, and the capture function itself do not create misleading change signals.
- Do not equate a quiet window with completed assistant output, and do not automatically submit conversations or overwrite Entries during this first experiment.

As of 2026-09-25, the remote `main` branch contains manual capture and fingerprint-based request skipping; `observer.js` and `service-worker.js` have not been added. Auto-capture remains unverified.

## Identity

Where a trustworthy stable conversation identifier can be obtained, repeated capture should reuse the existing external identity rule:

```text
(user_id, provider, external_id)
```

For a mutable conversation:

```text
first capture
→ INSERT

later capture of same conversation
→ UPDATE
```

This is especially important for conversations that continue after the first capture.

## Browser scope

A Chromium extension may cover Chrome and potentially Chromium-derived browsers such as Edge, Brave, and Arc with limited additional work.

Safari and Firefox should be treated as separate compatibility targets and are not part of the first PoC.

Browser capture never implies mobile-app capture.

---

# 2. Mobile Quick Capture

A third-party mobile app generally cannot inspect another app's private UI or internal conversation database in the background.

Therefore the realistic generic mobile mechanism is user-initiated sharing:

```text
Source mobile app
      |
      v
Share
      |
      v
lifhop Share Extension / Share Target
      |
      v
Capture API
      |
      v
Common ingestion pipeline
```

The lifhop share target can receive only the data that the source app and operating system actually expose through the share action, for example:

```text
text
URL
file
image
```

It must not be assumed that sharing from an AI app exposes the complete conversation text.

## ChatGPT mobile limitation

At the time this strategy was written, ChatGPT mobile sharing may provide a shared conversation link rather than the raw transcript to the receiving app.

Therefore:

```text
Share -> lifhop
```

is a valid low-effort UX concept, but:

```text
shared URL -> reliable full conversation extraction
```

must be treated as a separate technical and policy feasibility question.

The product must not promise automatic ChatGPT-mobile history ingestion until the acquisition path is verified and considered acceptable for commercial use.

---

# 3. Official Connected Sync

Providers that expose official OAuth/API/webhook mechanisms should use those mechanisms rather than browser scraping whenever practical.

Likely candidates:

```text
Notion
GitHub
Google Drive
other provider APIs as they become available
```

Desired user experience:

```text
Connect provider once
      |
      v
initial sync
      |
      v
lifhop becomes usable
      |
      v
incremental updates happen automatically
```

Possible synchronization mechanisms:

```text
Webhook
- provider pushes changes

Cursor-based API sync
- lifhop requests only changes after a cursor

Timestamp-based incremental sync
- external_updated_at > last_synced_at

Periodic polling
- fallback when webhooks/cursors are unavailable
```

Initial synchronization should also retrieve useful existing history where the official API permits it. In that case, initial sync naturally provides historical backfill without requiring export archives.

---

# 4. Developer Native Capture

For developer-heavy users, the lowest-effort source may be a native integration rather than a browser extension.

Potential integrations:

```text
Codex
Claude Code
Cursor
other coding agents
```

Possible mechanisms:

```text
MCP
plugin
session-completion hook
CLI hook
SDK / event integration
```

Conceptual flow:

```text
Developer session
      |
      v
native hook / integration
      |
      v
lifhop capture
      |
      v
DevSession / Conversation canonical data
```

This can capture structured information such as repository context, prompts, responses, commands, tool calls, and timestamps without requiring a user to export sessions manually.

Exact support depends on what each tool officially exposes.

---

# 5. Later Capture Options

These are useful but should not delay the core search and capture validation work.

## Local / Folder Sync

```text
Obsidian vault
Markdown directory
local document folder
        |
        v
Desktop watcher
        |
        v
changed files only
        |
        v
lifhop
```

This likely requires a desktop agent or local companion application.

## Email Forwarding / Mail Capture

Possible low-friction options include:

```text
forward message to a lifhop ingestion address
```

or, later:

```text
connect mail provider
→ ingest only user-selected labels / rules / senders
```

Mail should be treated carefully because broad automatic mailbox ingestion creates significant privacy and security scope.

---

# Historical Import Is Optional Enrichment

Existing ChatGPT export ZIP support remains useful and should not be removed.

Its product role changes from:

```text
required onboarding path
```

to:

```text
optional historical enrichment / migration path
```

Desired product flow:

```text
Sign up
   |
   v
Start capturing new records immediately
   |
   v
Use lifhop
   |
   +--> optionally connect providers with historical API access
   |
   +--> optionally import old exports later
```

This avoids blocking first value on export generation time.

Historical imports remain especially useful when:

- a provider has no history API
- a user wants older records from before continuous capture was enabled
- an account is being migrated
- a parser needs to reconstruct information that continuous capture did not retain

---

# Candidate Persistent Source Model

A future persistent source connection may evolve toward a model such as:

```text
SourceConnection
- id
- user_id
- provider
- capture_mode
- status
- external_account_id
- last_synced_at
- sync_cursor
- metadata
- created_at
- updated_at
```

Possible status values:

```text
ACTIVE
PAUSED
DISCONNECTED
ERROR
```

This is a design direction, not a committed Step 6 schema.

Do not add the model only to make the architecture look complete. Introduce it when the first ongoing capture/productization workflow demonstrates the actual fields and lifecycle required.

Likewise, continuous capture may eventually require a provider-neutral raw `CaptureArtifact`, `SourceRecord`, or evolution of the current `ImportArtifact`. Do not force browser events, webhook payloads, and uploaded ZIP files into one model before concrete capture workflows reveal the right abstraction.

---

# Coverage and Capture State

Low-effort capture can still produce an incomplete archive.

Example:

```text
ChatGPT Web via browser extension
→ captured

ChatGPT iOS app
→ not automatically captured
```

lifhop must not silently turn partial capture into a claim of complete history.

Later productization should retain enough capture-state metadata to answer questions such as:

```text
Which source is connected?
From what date is it captured?
When was it last synced?
Is automatic capture enabled?
Are there known unsupported surfaces?
```

This is important both for user trust and for later archive-wide analysis.

---

# Risk Register

## 1. Repeated user effort

**Risk:** Export/download/upload workflows are too cumbersome for ongoing use and become worse as the number of providers grows.

**Direction:** Treat exports as optional historical enrichment. Prefer connected sync, native capture, browser capture, or one-action share flows for ongoing records.

## 2. Export latency

**Risk:** A provider may take a long time to generate an export, delaying onboarding and first value.

**Direction:** Do not require a historical export before the user can start using lifhop. Begin capturing new records immediately.

## 3. Browser dependency

**Risk:** Browser extensions only capture activity on supported browser surfaces.

**Example:** ChatGPT Web in a supported Chromium browser may be captured while ChatGPT mobile-app conversations are missed.

**Direction:** Browser capture is one capture client, not the global ingestion strategy.

## 4. Mobile capture gap

**Risk:** lifhop cannot generally read another mobile app's private content automatically.

**Direction:** Use Share Extensions / Share Targets for low-effort explicit capture, and official provider APIs when available. Do not imply hidden cross-app access.

## 5. DOM and UI fragility

**Risk:** A web capture implementation that depends on DOM structure can break whenever the provider changes its UI.

**Direction:** Isolate provider-specific extraction logic, keep regression fixtures/tests, detect capture failure, and prefer official APIs when they become available.

## 6. Provider terms and policy

**Risk:** Technically possible browser extraction or programmatic retrieval may conflict with provider terms, automated extraction restrictions, platform policies, or future policy changes.

**Direction:** Treat policy/legal acceptability as a separate go/no-go requirement from technical feasibility. A successful PoC does not automatically authorize production use. Review provider terms before commercializing a capture method.

## 7. Lack of official history APIs

**Risk:** Some consumer AI services do not expose a stable third-party API for full personal conversation history.

**Direction:** Do not make the entire product dependent on one unavailable API. Support provider-specific combinations of continuous capture, one-action capture, and historical import.

## 8. Shared-link limitations

**Risk:** Mobile AI apps may share only a URL. The URL may be a snapshot, may later become unavailable, may require particular access conditions, or may require web-page extraction rather than an official data API.

**Direction:** Treat shared-link ingestion as a separately evaluated acquisition method. Preserve acquired raw content when permitted and useful rather than relying indefinitely on the external URL.

## 9. Privacy and over-capture

**Risk:** Continuous capture can collect highly sensitive conversations, code, credentials, personal information, or content the user never intended to archive.

**Direction:** Automatic capture should be explicit opt-in. Provide source-level enable/disable or pause controls as the feature is productized. Minimize permissions and avoid capturing more than needed.

Future controls may include:

```text
pause capture
exclude domains / conversations / projects
manual delete
source disconnect
capture status indicator
```

## 10. Security scope

**Risk:** OAuth tokens, captured conversations, mail, developer sessions, and private documents make lifhop a high-value sensitive-data store.

**Direction:** Use least-privilege scopes, secure token storage, encryption where appropriate, strict ownership checks, auditability, and explicit deletion/retention policies as connected capture is introduced.

## 11. Incomplete archive / coverage bias

**Risk:** If only some devices or surfaces are captured, later analysis may overstate patterns based on incomplete data.

**Direction:** Track source connection/capture range and surface known gaps where they materially affect answers. Never equate "data lifhop has" with "everything the user did."

## 12. Provider fragmentation

**Risk:** Every provider may require a different acquisition method and lifecycle.

**Direction:** Standardize the downstream ingestion boundary, not the upstream acquisition implementation. Provider adapters should absorb source-specific details.

## 13. Incremental synchronization complexity

**Risk:** Continuous sources introduce create/update/delete events, replay, retry, ordering, cursor state, and duplicate delivery.

**Direction:** Reuse stable external identity and idempotent upsert where provider semantics permit it. Build incremental sync only after one provider proves the required state model.

## 14. Raw-source model mismatch

**Risk:** The current `ImportArtifact` is naturally file/archive-oriented. Browser captures and webhook events may not fit that model cleanly.

**Direction:** Preserve raw source material where useful, but defer the exact continuous-capture artifact schema until real workflows exist.

## 15. Maintenance burden

**Risk:** Supporting many browser sites, APIs, mobile paths, and native tools can become a permanent maintenance project.

**Direction:** Prioritize capture methods by user value and stability. Do not promise uniform automation across every provider. Prefer a small number of reliable integrations over a broad but fragile catalog.

## 16. Intellectual-property and competitive implementation risk

**Risk:** Other products may implement similar browser capture, AI-memory, or archive workflows. Specific third-party code, UI, branding, or patented technical claims may create IP issues even when the broad product idea is common.

**Direction:** Design and implement lifhop independently. Do not copy competitor source code, distinctive UI, wording, or proprietary implementations. Keep architecture decisions and development history in the repository. Before commercial launch, consider targeted freedom-to-operate/patent review for the final core capture and retrieval mechanisms.

---

# Implementation Sequence

The agreed sequence is intentionally split between **early risk validation** and **later productization**.

```text
Step 6
Async Processing with SQS
        |
        v
Step 6.5
ChatGPT Web Capture PoC
- prove active-conversation extraction
- prove stable identity / upsert
- test update detection
- test opt-in auto-capture feasibility
- document browser/DOM/policy limitations
        |
        v
Steps 7-10
Search / RAG / Hybrid / Global Retrieval
- prove that collected records produce useful answers
        |
        v
Low-effort Capture Productization
- SourceConnection as required by real flows
- Chromium extension stabilization
- mobile Share Extension / Share Target
- capture controls and source state
- historical import repositioned as optional enrichment
        |
        v
Connected Sources
- OAuth / API / webhook
- initial + incremental sync
- Notion / GitHub / Drive candidates
        |
        v
Capture Expansion
- native MCP / hooks / plugins
- additional AI providers
- Safari / Firefox if justified
- local folder sync
- email forwarding
```

The key sequencing rule is:

> Validate ChatGPT Web continuous capture early, but do not let capture productization delay validation of lifhop's search and record-analysis value.

---

# ChatGPT Web PoC — Success Criteria

The Step 6.5 PoC is successful if it can demonstrate all of the following in a development environment:

- a Chromium extension can identify the active ChatGPT conversation
- user and assistant text required by the initial conversation model can be extracted
- the conversation can be submitted to lifhop without using an export ZIP
- repeated capture of the same conversation updates the existing Entry rather than duplicating it
- newly added messages can be detected reliably enough to evaluate auto-capture
- an opt-in automatic capture path can be demonstrated or conclusively rejected
- provider-specific extraction code is isolated from canonical normalization
- browser-only coverage and mobile gaps are documented
- DOM fragility and provider-policy/legal questions are documented before any production commitment

Current status (2026-09-25): manual extraction, API persistence, stable-identity upsert, and button-triggered fingerprint-based change detection have been verified. Background DOM observation and automatic capture feasibility remain open; do not select a final GO / LIMITED GO / NO-GO outcome until those risks have been evaluated.

The PoC should finish with a deliberate decision:

```text
GO
- continue toward browser capture productization

LIMITED GO
- retain one-click capture but do not auto-capture

NO-GO
- keep ChatGPT export/history import only until a safer official path exists
```

---

# Non-goals for the Early PoC

Do not expand Step 6.5 into a second full application project.

Not required:

- Chrome Web Store release
- Safari support
- Firefox support
- iOS application
- Android application
- polished onboarding
- generalized SourceConnection schema
- support for every AI website
- production legal approval
- perfect resilience to every UI change

The goal is to remove uncertainty early, document the risks, and then return to the core search roadmap.
