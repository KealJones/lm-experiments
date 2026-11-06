GIST
Long casual session with the user, an engineer (scattered, swears, goes in circles) debugging CI-only failures in the billing-ui package of a monorepo, mixed with fantasy football and dentist anxiety. This message is the culprit finally surfacing in the log.

REFERENCES RESOLVED
- "the thing again but different" = another laptop-passes/CI-fails test, after three earlier flaky-test fixes (missing await, unreset jest.spyOn mock, test ending before async work). Those were nondeterministic; this one is deterministic.
- "priyas new test" = "formats the due date column" in packages/billing-ui InvoiceTable.test.tsx, added about 2 days ago by Priya (not on the user's team). It was green on the last commit before hers. The user rebased, ran it locally, and it passed.
- "why" = why CI output differs from laptop output for the same instant.

RELEVANT FACTS
- The user mentioned earlier, unprompted, that the CI workflow env block sets TZ=UTC and his laptop is on US Central time. He said it "might matter later," and the assistant said to keep it in mind if a formatted date ever appeared. That is now. The user had also said "none of this touched dates" about the earlier failures. That was true then, and it is not true now.
- Stack: jest 29.7, Node 20 on both CI and laptop. Per-package jest.config.ts. clearMocks: true is now on. setupTests throws on console.error.
- The earlier causes (mocks, awaits, act warnings) are NOT in play here, and the assistant already told him that.
- Another teammate's date range picker test (a different package) broke on a locale difference. He fixed it by pinning en-US, and the user said no timezone pin was needed there. The assistant had suggested pinning timezone as well. The user's guess that a shared-utils formatDate change caused it was wrong: it was only a refactor.
- Date check: 2026-11-01T03:30:00Z is 10:30 PM Oct 31 in US Central (CDT, UTC-5) and 3:30 AM Nov 1 in UTC. The user's "Expected" string is the Central rendering and "Received" is the UTC rendering. Priya's expected value was therefore probably generated on a Central laptop, or she is in a non-UTC zone. DST ends in the US on Nov 1, 2026, which does not change this particular case.

USER PREFERENCES
- Has trouble with long walls of text and process; give the cause and the fix concisely.
- Pushes straight to main on his own repos, but uses PRs at work (this is a work repo).
- Do not nitpick his loose wording.
