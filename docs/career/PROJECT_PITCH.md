# Talking about CampusMatch

Use this to put the project on your resume and to talk about it in interviews. Before you use any
of it, read the code until you can explain each part without looking. Interviewers will ask
follow-up questions.

## Resume bullets

Pick 2–3. Each one says what you built, how you built it, and the evidence.

- Built **CampusMatch**, a compatibility-matching service for college students (Python,
  FastAPI). It scores matches with importance-weighted preferences and a geometric-mean match
  formula, and serves ranked recommendations with per-question explanations.
- Implemented **Irving's stable roommates algorithm** to split groups into roommate pairs with no
  "blocking pair." Verified it against brute-force enumeration on 510 random instances, and added
  a provably stable greedy fallback for groups where no stable pairing exists.
- Designed a REST API with 9 endpoints, input validation and pagination, plus a dependency-free
  JavaScript UI. Set up CI (GitHub Actions: lint, 35 tests, benchmark on Python 3.10–3.13) and a
  Docker image.
- Profiled performance: about 250k pair scores per second, and pairing 500 students in about 2.5
  s. Documented a scaling plan: vectorized scoring, a cached score matrix, candidate pre-filtering.

Format on your resume:

```
CampusMatch | Python, FastAPI, JavaScript, GitHub Actions, Docker     github.com/<you>/CollegeOkCupidProject
• <bullet 1>
• <bullet 2>
```

## 30-second pitch

> "I built a matching app for college students, sort of OkCupid for roommates. Students answer
> lifestyle questions, say which answers they'd accept, and weight how much each one matters.
> Recommendations were the easy part. The interesting part was splitting a whole dorm into
> pairs. I used Irving's stable roommates algorithm, so no two people would both rather swap.
> I learned that, unlike stable marriage, a stable solution doesn't always exist. In my data it
> disappeared for larger groups. So I added a fallback and proved it's stable on the mutual
> score. I tested the algorithm by brute-forcing every possible pairing on hundreds of random
> cases."

## 2-minute walkthrough

Give it in this order: **problem → approach → hardest part → how you verified it → what you'd do
next.**

1. **Problem.** Random roommate assignment produces bad pairings. Students care about different
   things to different degrees.
2. **Scoring.** For each question I record my answer, the answers I'd accept, and an importance
   weight from 0 to 250. My satisfaction with you is the weighted fraction of my preferences you
   meet. The match score is the geometric mean of both directions, minus a 1/n margin of error so
   that people with few shared answers don't rank too high.
3. **Hardest part.** Pairing a whole group. Preferences are asymmetric, so I used Irving's
   algorithm. Phase 1 is proposals; phase 2 removes rotations.
4. **Verification.** I wrote a brute-force enumerator that tries every possible pairing for up
   to 8 people. On random inputs, Irving's answer always agreed with it.
5. **Surprise and fix.** At 400 students, none of my random test groups had a stable pairing.
   So I added a greedy pairing on the mutual score and proved it can't contain a blocking pair
   with respect to that score.
6. **Next.** Postgres persistence, authentication, and vectorized scoring.

## Likely interview questions, with answers

**Why a geometric mean and not an average?**
It punishes lopsided matches. With satisfactions of 100% and 40%, the average is 70% and the
geometric mean is 63%. If either side is at 0, the match is 0.

**What's the time complexity?**
Scoring one pair is O(q), where q is the number of questions. Top-k for one user is O(n·q +
n log k) using a heap. Pairing builds n preference lists, which is O(n² log n). Irving's
algorithm is O(n²) in theory, but my version uses `list.remove`, which adds a factor of n. A
linked-list or index-pointer version would fix that.

**Why can the roommates problem have no stable solution when stable marriage always has one?**
In stable marriage the two sides are separate, and Gale–Shapley proposals always terminate in a
stable matching. In roommates, anyone can pair with anyone, so preferences can form cycles. The
classic counterexample: A prefers B, B prefers C, C prefers A, and everyone ranks D last.
Whoever ends up with D forms a blocking pair with someone.

**Why is the greedy fallback stable?**
Process pairs from the highest score down. Suppose X and Y aren't paired but both would prefer
each other by score. When the greedy reached the X–Y edge, one of them must already have been
paired, at a score at least as high. That contradicts "both prefer." This only works because the
score is symmetric.

**How did you test it?**
I wrote unit tests for the scoring math with hand-computed values. I checked the algorithm
against brute force on random inputs, which is property-style testing. I added the known
unsolvable and textbook instances, and API tests for validation, 404s and pagination.

**How would you scale this to 100k students?**
- Don't score all pairs. Filter candidates first by school, year or housing area.
- Store answers as bitmasks per question so scoring is vectorized (NumPy or SQL).
- Precompute and cache top-k, and recompute only when a profile changes.
- Replace the in-memory store with Postgres. The `Store` class is the only place that changes.

**What would you do differently?**
I'd start with a real database, since in-memory storage was a shortcut. I'd also add
authentication. With real data I'd learn the importance weights from outcomes, such as which
pairs students actually accept.

**What was hardest?**
Getting phase 2 of Irving's algorithm right: finding a rotation and removing it symmetrically
from both people's lists. The brute-force test is what gave me confidence it was correct.

## Before you use this in an interview

- [ ] Run `campusmatch serve` and click through the UI so you can demo it live.
- [ ] Trace Irving's algorithm by hand on the 6-person example in `tests/test_matching.py`.
- [ ] Be able to whiteboard `satisfaction()` and `score()` from memory.
- [ ] Change one thing yourself, for example add a question or a new endpoint, so the project is
      genuinely yours to talk about.
- [ ] Pin the repo on your GitHub profile and make sure the CI badge is green.
