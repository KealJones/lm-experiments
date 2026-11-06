GIST: The user is an engineer chasing CI failures in packages/billing-ui of a monorepo (Jest 29.7, Node 20, per-package jest.config.ts, React Testing Library). Earlier flakes were fixed: async assertions switched to findByText, a shared spy moved into beforeEach with clearMocks: true, and a test made to await its final state. He is now facing a new failure that is deterministic, not flaky. He is scattered (says his brain is on max), so short, one-step guidance works better.

REFERENCES RESOLVED: "priyas new test" is "formats the due date column" in InvoiceTable.test.tsx, added about two days ago by Priya, who is not on the user's team. "the thing again but different" is a new CI-only failure, not one of the earlier flakes. "the log" is the CI output he has now partly pasted.

RELEVANT FACTS:
- The test does new Date('2026-11-01T03:30:00Z') and formats it with toLocaleString() and no timezone argument.
- CI failure: Expected "Oct 31, 2026, 10:30 PM", Received "Nov 1, 2026, 3:30 AM". It fails every run on CI and passes on the user's laptop. The commit before Priya's test was green.
- The user's laptop is on US Central time. The CI workflow sets TZ=UTC in its env block. Earlier he said this did not matter because no tests touched dates. That is superseded, since this test formats a date.
- The strings line up with the two zones: 03:30 UTC on Nov 1 is 10:30 PM on Oct 31 in Central Daylight Time (UTC-5), which matches the expected value. The received value is UTC. US DST ends Nov 1, 2026 at 07:00 UTC, so the Central offset still applies at 03:30 UTC. These conversions are derived from the logs, not from a run.
- No one has yet run the test with TZ=UTC locally, and nothing has changed in the test since it was added.
- A teammate's date-picker failure was a locale issue, which he fixed by pinning en-US. A formatDate change in shared utils was only a refactor, not a behavior change, so it is probably unrelated.
- Other config: testTimeout 10000, and setupTests makes console.error throw.
