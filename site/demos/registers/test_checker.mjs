// node site/demos/registers/test_checker.mjs : replay data/checker_cases.json (from the Python checker) through world.js
import fs from "fs";
import { makeSkins, Sim } from "./world.js";
const here = new URL(".", import.meta.url);
const data = JSON.parse(fs.readFileSync(new URL("data/registers.json", here)));
const cases = JSON.parse(fs.readFileSync(new URL("data/checker_cases.json", here)));
const S = makeSkins(data);
let bad = 0, steps = 0;
for (const c of cases) {
  const sim = new Sim(c.ep, c.ep.skin, S, { places: data.places, doorPlaces: data.door_places });
  for (let i = 0; i < c.trace.length; i++) {
    const inject = sim.step(c.sents[i].split(" "));
    const want = c.trace[i];
    steps++;
    if (sim.status !== want.status || sim.why !== want.why || (inject ?? null) !== want.inject) {
      bad++;
      console.log("MISMATCH", c.sents[i], { js: [sim.status, sim.why, inject], py: want });
      break;
    }
  }
}
const ends = cases.map((c) => c.trace.at(-1)?.why || c.trace.at(-1)?.status || "unfinished");
const tally = {}; ends.forEach((e) => (tally[e] = (tally[e] || 0) + 1));
console.log(`${cases.length - bad} of ${cases.length} plans agree (${steps} sentences)`, tally);
process.exit(bad ? 1 : 0);
