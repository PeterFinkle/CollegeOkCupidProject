"""Command line entry point.

campusmatch demo   [--students N] [--seed S]   show sample recommendations
campusmatch pair   [--students N] [--seed S]   stable roommate pairing
campusmatch bench  [--students N]              time scoring (pure Python and NumPy) + pairing
campusmatch serve  [--host H] [--port P] [--db PATH]
                                               run the web app (in memory, or on a SQLite file)
"""

from __future__ import annotations

import argparse
import statistics
import time

from .data import generate_students
from .matching import pair_roommates, top_matches
from .scoring import score


def _demo(args: argparse.Namespace) -> None:
    students = generate_students(args.students, seed=args.seed)
    for me in students[:3]:
        print(f"\nTop matches for {me.name} ({me.major}, year {me.year}):")
        for other, s in top_matches(me, students, k=5):
            print(
                f"  {s.percent:3d}%  {other.name:<18} {other.major:<20} "
                f"(you->them {s.satisfaction_a:.0%}, them->you {s.satisfaction_b:.0%})"
            )


def _pair(args: argparse.Namespace) -> None:
    students = generate_students(args.students, seed=args.seed)
    by_id = {s.id: s for s in students}
    pairing = pair_roommates(students)
    done, scores = set(), []
    for a, b in sorted(pairing.pairs.items()):
        if b is None:
            print(f"  unpaired: {by_id[a].name}")
        elif a not in done:
            done.update((a, b))
            pct = score(by_id[a], by_id[b]).percent
            scores.append(pct)
            print(f"  {pct:3d}%  {by_id[a].name:<18} + {by_id[b].name}")
    how = (
        "stable on individual preferences (Irving)"
        if pairing.method == "irving"
        else "no stable pairing exists; used greedy pairing on mutual score"
    )
    print(f"\n{len(scores)} pairs, median match {statistics.median(scores):.0f}% - {how}")


def _bench(args: argparse.Namespace) -> None:
    students = generate_students(args.students, seed=1)
    n = len(students)
    t0 = time.perf_counter()
    for s in students:
        top_matches(s, students, k=10)
    pure = time.perf_counter() - t0
    print(
        f"{n} students: all-pairs recommendations {pure:.3f}s "
        f"({n * (n - 1) / pure:,.0f} pair scores/s, pure Python)"
    )

    try:
        from .fast import encode, top_matches_fast
    except ImportError:
        print("numpy not installed; skipping the vectorized path (pip install campusmatch[fast])")
    else:
        # Same work as above: score every pair, then take each student's top 10.
        t0 = time.perf_counter()
        arrays = encode(students)
        matrix, shared = arrays.match(), arrays.shared()
        for i in range(n):
            top_matches_fast(i, matrix, k=10, shared=shared)
        vec = time.perf_counter() - t0
        print(
            f"{n} students: all-pairs recommendations {vec:.3f}s "
            f"({n * (n - 1) / vec:,.0f} pair scores/s, NumPy) - {pure / vec:.0f}x faster"
        )

    t0 = time.perf_counter()
    pairing = pair_roommates(students)
    print(f"roommate pairing ({pairing.method}) in {time.perf_counter() - t0:.2f}s")


def _serve(args: argparse.Namespace) -> None:
    import uvicorn

    from .api import create_app

    if args.db:
        print(f"Storing profiles in SQLite at {args.db}")
    uvicorn.run(create_app(db_path=args.db), host=args.host, port=args.port, reload=False)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="campusmatch",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, fn, default_n in (("demo", _demo, 200), ("pair", _pair, 20), ("bench", _bench, 500)):
        p = sub.add_parser(name)
        p.add_argument("--students", type=int, default=default_n)
        p.add_argument("--seed", type=int, default=42)
        p.set_defaults(fn=fn)
    p = sub.add_parser("serve")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument(
        "--db", metavar="PATH", help="SQLite file to keep profiles in (default: in memory)"
    )
    p.set_defaults(fn=_serve)
    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
