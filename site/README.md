# The lab site

A static site built from `experiments/`, published to GitHub Pages by `.github/workflows/site.yml` on every push to main.

- `build.py` turns every `experiments/<name>/` folder into an entry on the index: title, question, finding, a
  "show the numbers" table, run note, date and status, all read from the folder's README. A new experiment
  appears on the next push with nothing else to do. See the top of `build.py` for what it reads and for
  `demo.json`, the optional per-experiment file that promotes one to a demo or fixes a bad guess.
- `lab.css` is shared by every page.
- `demos/<name>/` holds hand-built demo pages. `demos/loop-concept/` is the first: Plink runs in the browser
  (`plink.js`, checked against `plink.py` by `test_plink.py`), and `build_data.py` turns the raw results into
  `data/*.json`. Rerun it when loop-concept gets new results.

Preview: `python3 site/build.py && python3 -m http.server -d site/dist`, then open http://localhost:8000.
