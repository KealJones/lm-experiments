Yeah, this one's not a flake, it's the timezone thing I said to keep an eye on. It's the first date test in that file, and it's doing exactly what you'd expect.

Do the math:

- `2026-11-01T03:30:00Z` is 3:30 AM UTC on Nov 1.
- CI has `TZ=UTC` in its env block, so `toLocaleString()` with no `timeZone` gives **"Nov 1, 2026, 3:30 AM"**. That's your Received.
- Your laptop is on Central. Nov 1, 2026 is the day DST ends, but that doesn't happen until 2 AM local (07:00 UTC). So at 03:30 UTC you're still on CDT (UTC-5), which gives **"Oct 31, 2026, 10:30 PM"**. That's the Expected.

So Priya almost certainly ran it on her own machine (Central, or at least UTC-5 right then), copied whatever string came out, and hardcoded it. It passes anywhere that's UTC-5 at that moment and fails anywhere else, every single time. Deterministic. Keep it out of #flake-watch.

And she managed to pick a timestamp that crosses midnight, the month boundary *and* the DST changeover all at once. Honestly a great test case. It's just pinned to whatever clock happened to run it.

I'm gonna push back on "the teammate didn't need it" too. His date picker tests probably used dates where the offset didn't change the output, or dates built in local time. You can get away without pinning TZ until one of your dates sits near midnight, and then it bites you just like this.

**Fix: make the timezone explicit, don't just swap the string.** Two ways:

1. **Pin TZ for Jest everywhere** so laptops match CI. Do it in a `globalSetup` in the shared jest config (`process.env.TZ = 'UTC'`), or put `TZ=UTC` in the test script. Don't set it in `setupFiles`. By then it can be too late in the process to stick reliably. Then change Expected to `"Nov 1, 2026, 3:30 AM"`.
2. **Pass `timeZone` explicitly** wherever the formatting happens, e.g. `toLocaleString('en-US', { timeZone: 'America/Chicago' })`, or whatever the component should actually use. Then nobody's machine settings matter.

Which one you pick depends on something only you all can answer: **is the due date column supposed to show the viewer's local time, or a fixed zone?** If it's the viewer's local time, the component is fine and the test just needs a pinned TZ (option 1). If a due date is really a calendar day, though, someone in UTC-8 is gonna see an invoice due a day early, and that's a real bug the test is accidentally showing you. Worth a quick question to Priya.

One more thing: if this fails every time on CI, how did it get merged? Check whether CI actually ran (and passed) on her PR, or whether it went in with a red or skipped check. That's a separate problem worth knowing about.
