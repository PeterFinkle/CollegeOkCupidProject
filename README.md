# CampusMatch

[![CI](https://github.com/PeterFinkle/CollegeOkCupidProject/actions/workflows/ci.yml/badge.svg)](https://github.com/PeterFinkle/CollegeOkCupidProject/actions/workflows/ci.yml)

CampusMatch matches college students for compatibility. Students answer lifestyle questions, say
which answers they'd accept from someone else, and rate how much each question matters. The app
then does two things:

1. **Ranked recommendations.** It gives each student a ranked list of their best matches, with a
   per-question explanation of each score.
2. **Roommate pairing.** It splits a whole group into roommate pairs using **Irving's stable
   roommates algorithm**. The result is a pairing where no two students would both rather room
   with each other than with their assigned partners. When no such pairing exists, it falls back
   to a greedy pairing that is provably stable on the mutual match score.

It's a Python library, a REST API (FastAPI), a CLI, and a small web UI with no dependencies. It
has 35 tests, including a brute-force check of the pairing algorithm against every possible
pairing on random inputs.

<img src="docs/img/matches.png" alt="Ranked matches with a per-question breakdown" width="640">

## Quick start

```bash
pip install -e ".[dev]"
campusmatch serve            # web UI at http://127.0.0.1:8000, API docs at /docs
campusmatch demo             # top matches for a few synthetic students
campusmatch pair --students 20
campusmatch bench --students 500
pytest -q
```

Or with Docker: `docker build -t campusmatch . && docker run -p 8000:8000 campusmatch`.

## How scoring works

For every question both students answered:

| Step | Formula |
|---|---|
| Importance weights | irrelevant 0, a little 1, somewhat 10, very 50, mandatory 250 |
| A's satisfaction with B | Σ A's weight where B's answer is acceptable to A ÷ Σ A's weight |
| Match | √(sat_A × sat_B) − 1/n_shared, floored at 0 |

Three reasons for this design:

- **Geometric mean.** It punishes one-sided matches. A 100% / 40% pair scores 63%, where an
  arithmetic mean would give 70%. Compatibility should require both people to be happy.
- **Geometric importance weights.** One "mandatory" question outweighs dozens of trivial ones, so
  it works almost like a dealbreaker. It still isn't a hard filter, which keeps everyone matchable.
- **Margin of error (−1/n).** It keeps two people who agree on a single question from showing up
  as a "100% match" ahead of people who agree on 11 out of 12.

## How roommate pairing works

Ranking matches for one person is easy. Splitting a whole dorm into pairs is the interesting
part. Each student ranks everyone else by how well the other student's answers satisfy *their
own* preferences. That ranking is **asymmetric**: Alex can rank Sam first while Sam ranks Alex
last.

- `stable_roommates()` implements Irving's two-phase algorithm (1985). Phase 1 is a round of
  proposals and rejections. Phase 2 finds and removes "rotations" until every preference list has
  one entry left. It either returns a stable pairing or proves that none exists.
- Unlike stable *marriage*, the roommates problem can have **no** stable solution. In this
  project's synthetic data, a stable pairing existed for 4 of 5 random groups of 20 students, 2 of
  5 groups of 100, and 0 of 5 groups of 400. When none exists,
  `pair_roommates()` falls back to `greedy_pairs()`, which pairs students by descending mutual
  score. The mutual score is symmetric, so this greedy pairing is stable with respect to it: no
  pair outside the result has a higher score than both of their assigned partners.
- An odd-sized group gets a sentinel "nobody" that everyone ranks last, so exactly one student is
  left unpaired.

### How it's verified

`tests/test_matching.py` enumerates every perfect matching for random inputs with n = 2, 4, 6
and 8 people (up to 105 matchings each, 510 random instances in total). It checks that whenever
Irving returns a pairing, that pairing is stable, and that whenever Irving returns `None`, no
stable pairing exists. It also covers the classic unsolvable 4-person instance and the textbook
6-person example.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/questions` | Question bank |
| GET | `/importance-levels` | Importance names and weights |
| POST | `/profiles` | Create a profile with answers (validated; returns 422 with a reason) |
| GET | `/profiles?limit&offset` | Paginated list |
| GET | `/profiles/{id}` | One profile |
| GET | `/profiles/{id}/matches?k=10` | Top-k matches, both directions of satisfaction |
| GET | `/compare/{a}/{b}` | Score plus a per-question breakdown, disagreements first |
| POST | `/roommates` | Body: list of ids. Returns pairs, unpaired student, and method used |
| GET | `/health` | Liveness check |

Interactive docs are at `/docs` (OpenAPI).

## Performance

`campusmatch bench --students 500` on a laptop-class CPU:

- All-pairs recommendations: about 250k pair scores per second, about 1 s for 500 students.
- Roommate pairing: about 2.5 s for 500 students. Building the preference lists is O(n² log n).
  Irving runs in O(n²) list operations in principle; this implementation uses `list.remove`,
  which adds a factor of n.

At scale I'd change three things. I'd precompute per-question bitmasks so the score becomes a few
vectorized operations (NumPy, or SQL over an answers table). I'd cache the score matrix and
invalidate it per profile on update. And I'd narrow candidates first (same school year, housing
area) before scoring.

## Project layout

```
src/campusmatch/
  models.py     Question, Answer, Profile, Importance
  scoring.py    satisfaction, match score, explanation
  matching.py   top-k, Irving's algorithm, greedy fallback, stability check
  data.py       question bank + seeded synthetic population (persona-based)
  api.py        FastAPI app, in-memory thread-safe store
  cli.py        demo / pair / bench / serve
  static/       single-page UI (vanilla JS, light + dark mode)
tests/          scoring, matching (incl. brute-force), API
```

## Next steps

- Persist profiles in Postgres (the `Store` class is the only seam that needs replacing).
- Authentication, so each student can only edit their own profile.
- Learn importance weights from which matches students actually message or accept.
- Group housing (suites of 3–4), which is NP-hard in general and would need a heuristic or an ILP.

---

This repo also has a job-search kit in [`docs/career/`](docs/career/): resume bullets,
interview prep, and an application tracker.
