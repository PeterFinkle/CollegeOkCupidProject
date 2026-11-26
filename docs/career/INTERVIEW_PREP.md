# Interview prep

## 1. Coding interviews: a 4-week plan

Aim for roughly 1–2 hours a day. Practice by pattern, not at random. For each problem, spend 25
minutes on your own attempt. If you're stuck, read the solution, then re-solve it from scratch
two days later.

| Week | Patterns | Examples (search these names on LeetCode or NeetCode) |
|---|---|---|
| 1 | Arrays & hashing, two pointers, sliding window | Two Sum, Group Anagrams, Top K Frequent, Valid Palindrome, 3Sum, Longest Substring Without Repeating Characters |
| 2 | Stack, binary search, linked lists | Valid Parentheses, Daily Temperatures, Search in Rotated Sorted Array, Koko Eating Bananas, Reverse Linked List, LRU Cache |
| 3 | Trees, heaps, BFS/DFS on graphs | Max Depth, Lowest Common Ancestor, Level Order, Kth Largest, Number of Islands, Course Schedule |
| 4 | Intervals, greedy, 1-D DP, backtracking + mock interviews | Merge Intervals, Jump Game, Climbing Stairs, House Robber, Coin Change, Subsets |

**Say this out loud in every coding interview:**
1. Restate the problem and confirm the inputs, outputs and edge cases (empty input, duplicates,
   negative numbers).
2. Give the brute-force approach and its complexity first.
3. Explain the better approach *before* you write code, and get a nod from the interviewer.
4. Write clean code with clear names.
5. Walk through one example by hand, then test the edge cases.
6. State the final time and space complexity.

**Tie-ins to your project:** you've already implemented a heap-based top-k (`heapq.nsmallest`),
graph-style matching, and brute-force verification. Mention these when similar problems come up.

## 2. System design (for new-grad level)

New-grad interviews ask lighter versions. Practice this one using your own project:

> "Design a roommate-matching service for a university of 30,000 students."

- **Requirements:** create a profile, answer questions, see top matches, and let the housing
  office run pairing for each dorm. Reads far outnumber writes.
- **API:** reuse your actual endpoints from `api.py`.
- **Data:** `students`, `questions`, `answers(student_id, question_id, choice, acceptable_mask,
  importance)`.
- **Compute:** only score candidates in the same housing pool. Precompute top-k nightly and when a
  profile changes. Run pairing as a batch job per dorm.
- **Scale:** a cache in front of `/matches`, a job queue for pairing, read replicas.
- **Trade-offs:** how fresh the results are vs. compute cost; fairness (does the greedy fallback
  favor some students?); privacy (answers are sensitive, so access control matters).

## 3. Behavioral interviews: your story bank

Prepare 6–8 stories. Each story can answer several questions. Use **STAR**: Situation (1–2
sentences), Task, Action (most of your time, and say "I", not "we"), Result (numbers if possible,
plus what you learned).

| Story slot | Fill in from your experience | Answers questions like |
|---|---|---|
| Technical challenge | e.g. getting Irving's phase 2 right, verified by brute force | "Hardest bug?", "Something you're proud of?" |
| Ambiguity / self-directed | e.g. deciding what to do when no stable pairing exists | "When requirements were unclear?" |
| Teamwork | class project, club, job | "Worked with a difficult teammate?" |
| Failure / mistake | | "Tell me about a failure", "Missed a deadline?" |
| Leadership / initiative | | "Went above and beyond?", "Led something?" |
| Learning fast | | "Learned a new technology quickly?" |
| Feedback | | "Received critical feedback?" |
| Conflict / disagreement | | "Disagreed with a decision?" |

**Template:**
```
Title:
S:
T:
A: (3–4 concrete things I did)
R: (outcome + number + lesson)
```

**Questions you should have an answer for:**
- Tell me about yourself. (90 seconds: present → past → why this role.)
- Why this company? (Name something specific: a product, an engineering blog post, their mission.)
- Why are you leaving or looking? (Keep it forward-looking and positive.)
- Where do you see yourself in a few years?
- What are your salary expectations? (Research the range on levels.fyi or Glassdoor, give a
  range, and try to let them say a number first.)

## 4. Questions to ask your interviewers

Pick 2–3 for each interviewer.

- What does a new engineer's first 90 days look like?
- How is code reviewed and deployed here? How often do you ship?
- What's a recent technical challenge the team worked through?
- How do you measure success for someone in this role after a year?
- What do you like most about working here? What would you change?
- How do mentorship and growth work for junior engineers?

## 5. Day-of checklist

- [ ] Test your camera, mic and internet connection, and have a coding environment ready.
- [ ] Have the job description, your resume and your story bank open.
- [ ] Prepare a water bottle and a notepad.
- [ ] Join 3 minutes early.
- [ ] Send a short thank-you within 24 hours that mentions one specific thing you discussed.
