GIST: The user, an engineer who writes casually, has spent this long chat debugging CI-only Jest failures in packages/billing-ui (InvoiceTable.test.tsx) in his work monorepo. The chat also wandered into fantasy football, a dentist appointment he's dreading, and other side topics that don't matter here.

REFERENCES RESOLVED:
- "doing the thing again but different": another test that passes locally and fails on CI. The earlier ones were intermittent flakes. This one fails every time.
- "priyas new test": "formats the due date column" in InvoiceTable.test.tsx. Priya (not on his team) added it about 2 days ago. CI was green on the commit before hers.
- "it": CI.

RELEVANT FACTS:
- **Key environment difference:** the CI workflow sets TZ=UTC in its env block. His laptop runs on US Central time. He said that's the only way CI runs Jest differently. Back then the assistant said TZ only matters for tests that touch dates and to keep it in mind if a formatted date ever showed up. This is the first date test.
- Both environments run Jest 29.7 and Node 20, with per-package jest.config.ts. The root runs `yarn workspaces foreach`. testTimeout is 10000.
- Earlier fixes in the same file (all green on CI now), none of which apply here:
  - sync getByText changed to findByText
  - spy moved into beforeEach plus `clearMocks: true`
  - the "shows spinner then table" test now awaits the final state (setupTests throws on console.error)
- A teammate's date range picker tests in another package failed over a locale issue. He fixed them by pinning the locale to en-US. The assistant suggested also pinning timezone explicitly, and the user said the teammate "didn't need it."
- Nobody changed `formatDate` in shared utils. It was only a file refactor, so it isn't a regression source.
- The user had already rebased onto main before running the test locally, where it passed.
- He swears casually and is scattered today, so a clear, focused answer helps. At work they use PRs, and they're starting a #flake-watch Slack channel for flaky tests.
- Just before this message, the assistant asked for the exact Expected/Received lines, which he has now provided.
