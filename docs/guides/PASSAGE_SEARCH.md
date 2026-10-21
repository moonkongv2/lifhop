# Local passage search — Phase 3.2A

Search provides **Exact phrase** (existing default) and **Passages**. Passages ranks
matching words in current original text, without translation, embeddings or AI answers.
Codex primary search includes questions/answers; its work option additionally searches
commands, results, diffs and commentary. AI-denied records remain locally searchable.

## Setup and backfill

```bash
docker compose up -d db
.venv/bin/alembic upgrade head
.venv/bin/python scripts/index_passages.py --email YOUR_EMAIL
```

Enter the local lifhop password in the terminal. The CLI reports counts/cursor,
never original text. Use `--after CURSOR` to resume a capped run; use `--after 0`
to retry failed items. Ready/partial current projections are skipped. `--batch`
defaults to 20, `--max-entries` to 10,000. Deleted/concurrently edited records are
rechecked under owner-before-record locks. A failure leaves the source untouched.
Changing projection rules requires a new projection version and backfill.

Migration `d15e8a02b731` creates empty passage tables and pending state. It retains
all observed source versions. Old accounts require explicit backfill; new or edited
records are indexed in the source transaction. The selected `b@test.com` development
account already has 480 ready records from this implementation check.

Run the backend and frontend as usual, then open `http://localhost:5173/search`.
Passage search needs no import worker; uploads/purge still need the existing worker.

## Owner verification

1. Sign in, select **Passages**, search words present in the source, and apply filters.
   Empty input sends no search request. Results show actual source text and dates;
   titles matched alone are labeled separately.
2. Click **View passage**. Check its exact original text, version and character range.
   **Back to search** preserves query/filter/mode/page, including reload/new tabs.
   **Open record** opens the current record, rather than generating an answer.
3. Use **View … retained locations** on repeated GitHub document text. Exact version
   links load lazily and stay within the date/source filters. Counts mean retained
   snapshots/locations; they do not assert the current GitHub file.
4. Create a disposable note with a unique marker in its body. Search that marker,
   edit it to another unique marker, then delete the note. Old markers disappear;
   previous passage links become unavailable. Version restoration creates fresh
   passage IDs while keeping original versions unchanged.
5. Check coverage warnings separately from no matches. Input over 8 MiB, over 512
   passages, or invalid Codex mapping can leave a partial title-only index. Original
   records and Exact phrase remain available. Source-deleted content is excluded
   by default; selecting deleted source status includes labeled retained local text.

## Evaluation

```bash
.venv/bin/python scripts/evaluate_retrieval.py run --email YOUR_EMAIL --set SET_DIRECTORY --retriever passages --mode primary
.venv/bin/python scripts/evaluate_retrieval.py run --email YOUR_EMAIL --set SET_DIRECTORY --retriever passages --mode keywords
```

`--retriever literal` remains the default. The shared source/owner/database-bound
read-only evaluation does not approve candidates, edit gold, or invoke AI. Passage
scores require full pinned gold coverage in the same version/field. If multiple
ranked passages are necessary, the completion rank is the last required rank.
Exact verified snapshot aliases can supply that version, even beyond the card's
first five aliases. Other versions/partial similar passages do not become new gold.
Natural questions and independent auxiliary queries remain separate; failures stay
in denominators. Reports omit original text, questions, claims and annotations.

The frozen three-question pilot from one English README measured natural support
0/3 → 1/3 and auxiliary mean recall@20 1/3 → 1. Existing scores are Entry-level;
new scores require actual passage coverage. Korean→English questions still failed.
This is a limited lexical improvement and does not complete the diverse real set.

## Bounds and remaining work

Queries have 256 characters/16 distinct content tokens; pages have at most 50 items
and two displayed groups per representative Entry. DB grouping/counting precedes
pagination. Card aliases cap at five; location pages cap at 50. A shared five-second
retrieval deadline (plus at most two seconds waiting for the owner lock), bounded
source slices and 1 MiB response limit distinguish 503 failure from empty results.
Concurrent changes between requests can shift offset pages.

Current search does not retrieve historical selected versions. External embeddings,
pgvector, cost-controlled backfill and cross-language quality comparison remain 3.2B;
grounded generated answers remain 3.3. Development reads by the current Codex do
not enable runtime AI transmission or provide raw records to Antigravity.
