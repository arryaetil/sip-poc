# Business Context through chat

The launcher has no create/update dropdown. On a new conversation the existing
assistant resolves the user's intent against approved accessible contexts and
reviewed website titles/URLs. It returns an internal selection through the
existing ProductStrategistTurn message field; SIP validates that selection.
Unknown IDs, invalid responses and ambiguity produce a question in the chat.
Only Product Owner/admin can select an approved context for an update.

Context updates reuse the existing baseline, diff, versioning and review/save
flow. Merely selecting a context does not write a Business Context. A resolved
intent remains bound to the conversation across reloads. Older conversations
keep their previous create/update behaviour through an additive migration.

A website supplement starts with the reviewed website snapshot, not a live
crawl. It creates a separate Business Context for review/approval; the original
public website and corpus remain intact. The baseline is sent again for every
turn and finalization, and its source URL is preserved in the saved context.
Once approved it enters the existing knowledge index and Studio library.

Validation: route tests cover unknown IDs, ambiguity, normal update proposals,
website provenance on continuation and finalization. Three live calls through
the current Dify Strategist recognized create, update and website intent.
