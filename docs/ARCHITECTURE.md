# Architecture

```text
Visitor question → normalize → match approved aliases
                              ├─ one topic → stored answer and FAQ link
                              └─ zero or many → fallback and support route
                                                 └─ visitor opt-in → local queue

FAQ editor → draft → explicit approval → eligible for retrieval
                  approved edits → draft
```

`app.py` serves HTML and handles local form submissions. `assistant.py` contains retrieval and SQLite operations. `views.py` builds the conversation, FAQ source pages and editor. `knowledge.json` supplies four approved fictional FAQs and a draft example. Source links resolve to the approved record as it exists at the time of the click. An unpublished record returns 404.

Alias matching normalizes case and punctuation, then checks complete contiguous token phrases. Two matching records trigger an ambiguous fallback. A response uses the stored answer verbatim and includes the matching FAQ. The editor checks revision numbers before applying changes, so a stale review form cannot approve a newer draft.

State stays in the selected SQLite file. The queue keeps up to 100 opted-in unmatched or ambiguous questions. Clearing removes them from the visible queue and normal queries. It is not secure erasure. Input is escaped in HTML. The local listener checks the host, submission token and browser origin when present. Local processes and any person with local access are trusted. These controls do not provide authentication for a shared or hosted installation.

`evaluate.py` checks expected reason and topic against `eval_cases.json`. The separate HTTP tests verify how storage, citation visibility, the editor and opt-in tracking interact. Screenshots were captured from the running app with a fresh synthetic database.
