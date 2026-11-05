// The skins world's checker, ported from experiments/registers-v2/rv2.py (class Sim).
// It runs a plan one sentence at a time and fails it at the first sentence that doesn't fit the world.
// test_checker.mjs replays random plans through both versions and checks they agree.

export function makeSkins(data) {
  const home = data.skins.home;
  const c2s = {}, s2c = {}, wordsOf = {};
  const all = new Set();
  for (const [skin, words] of Object.entries(data.skins)) {
    c2s[skin] = Object.fromEntries(home.map((w, i) => [w, words[i]]));
    s2c[skin] = Object.fromEntries(words.map((w, i) => [w, home[i]]));
    wordsOf[skin] = new Set(words);
    words.forEach((w) => all.add(w));
  }
  const toSkin = (text, skin) => text.split(" ").map((w) => c2s[skin][w] ?? w).join(" ");
  const toHome = (words, skin) => words.map((w) => s2c[skin][w] ?? w).join(" ");
  return { c2s, s2c, wordsOf, all, toSkin, toHome };
}

const SENT = [
  ["search", /^search : where is the (\w+) \?$/],
  ["choose", /^the (\w+) wants the (\w+) because the \2 is (\w+) \.$/],
  ["needkey", /^the door of the (\w+) is locked , so the (\w+) needs the key \.$/],
  ["go", /^the (\w+) is not at the (\w+) , so the \1 goes to the \2 \.$/],
  ["open", /^the door of the (\w+) is closed , so the (\w+) opens the door of the \1 \.$/],
  ["unlock", /^the door of the (\w+) is locked , so the (\w+) opens the door of the \1 with the key \.$/],
  ["take", /^the (\w+) takes the (\w+) \.$/],
  ["check", /^the (\w+) has the (\w+) , so the goal is done \.$/],
  ["done", /^done \.$/],
];

export class Sim {
  constructor(ep, skin, skins, places) {
    this.ep = ep;
    this.skin = skin;
    this.S = skins;
    this.hasDoor = new Set(places.doorPlaces);
    this.allPlaces = new Set(places.places);
    this.here = ep.start;
    this.doors = { ...ep.doors };
    this.held = new Set();
    this.chosen = ep.prop ? null : ep.target;
    this.searched = new Set();
    this.status = null;
    this.why = "";
  }

  fail(why) { this.status = "fail"; this.why = why; return null; }

  // words: one finished sentence, in skin words. Returns skin text to add (a search result) or null.
  step(words) {
    if (words.some((w) => this.S.all.has(w) && !this.S.wordsOf[this.skin].has(w))) return this.fail("another skin's word");
    const inject = this._step(this.S.toHome(words, this.skin));
    return inject ? this.S.toSkin(inject, this.skin) : null;
  }

  _step(sent) {
    const ep = this.ep;
    let kind, m;
    for (const [k, rx] of SENT) { m = sent.match(rx); if (m) { kind = k; break; } }
    if (!kind) return this.fail("garbled");
    const g = m.slice(1);
    if (kind === "search") {
      if (!(g[0] in ep.loc)) return this.fail("bad search");
      this.searched.add(g[0]);
      return `result : the ${g[0]} is at the ${ep.loc[g[0]]} .`;
    }
    if (kind === "done") {
      const ok = this.chosen === ep.target && this.held.has(ep.target);
      this.status = ok ? "ok" : "fail";
      this.why = ok ? "" : "done without goal";
      return null;
    }
    const agent = ["needkey", "open", "unlock"].includes(kind) ? g[1] : g[0];
    if (agent !== ep.agent) return this.fail("wrong agent");
    if (kind === "choose") {
      if (!ep.prop || g[2] !== ep.prop || g[1] !== ep.target) return this.fail("wrong choice");
      this.chosen = g[1];
    } else if (kind === "needkey") {
      if (this.doors[g[0]] !== "locked") return this.fail("false claim");
    } else if (kind === "go") {
      if (!this.allPlaces.has(g[1]) || this.here === g[1]) return this.fail("bad go");
      this.here = g[1];
    } else if (kind === "open" || kind === "unlock") {
      const want = kind === "open" ? "closed" : "locked";
      if (this.here !== g[0] || this.doors[g[0]] !== want || (kind === "unlock" && !this.held.has("key"))) {
        return this.fail("bad " + kind);
      }
      this.doors[g[0]] = "open";
    } else if (kind === "take") {
      if (ep.loc[g[1]] !== this.here || (this.doors[this.here] ?? "open") !== "open") return this.fail("bad take");
      this.held.add(g[1]);
    } else if (kind === "check") {
      if (!this.held.has(g[1])) return this.fail("false claim");
    }
    return null;
  }
}

// What each failure means, in plain words
export const WHY = {
  "bad go": "It went somewhere it already was, or to a place that doesn't exist.",
  "bad take": "It took something that isn't here, or reached through a door that isn't open.",
  "bad open": "It opened a door that isn't here or isn't closed.",
  "bad unlock": "It unlocked a door that isn't here, isn't locked, or without holding the key.",
  "false claim": "It said something about the world that isn't true.",
  "wrong choice": "It picked the wrong thing for what the agent wants.",
  "wrong agent": "It made someone else act.",
  "bad search": "It searched for something that isn't in this world.",
  "done without goal": "It said done without holding the thing that was wanted.",
  "garbled": "The sentence isn't one the world understands.",
  "another skin's word": "It used a word from a different skin.",
  "too long": "It never finished.",
};
