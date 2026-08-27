"""``trace-batch`` console script: load a batch of events from a Delphes
ROOT file and write their polar/beam-axis displays to a directory, without
writing any Python.

Developed by Wasikul Islam, PhD.
"""

import argparse
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="trace-batch",
        description="Batch-generate TRACE event displays from a Delphes ROOT file.",
    )
    parser.add_argument("--input", required=True, metavar="FILE.root", help="Delphes ROOT file")
    parser.add_argument("--indices", required=True, nargs="+", type=int, metavar="N",
                         help="Event indices to draw, e.g. --indices 0 1 2")
    parser.add_argument("--outdir", required=True, metavar="DIR", help="Output directory")
    parser.add_argument("--which", nargs="+", default=["polar", "beam2d"],
                         choices=["polar", "beam2d"], help="Which display(s) to produce")
    parser.add_argument("--label", default="", help="Sample label stamped into plot titles")
    parser.add_argument("--show-tracks", action="store_true",
                         help="Also draw individual reconstructed tracks (polar view only)")
    args = parser.parse_args(argv)

    try:
        from .io.delphes import load_events
    except ImportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    from .batch import run_event_batch

    events = load_events(args.input, args.indices, label=args.label)
    if not events:
        print(f"error: no events loaded from {args.input}", file=sys.stderr)
        return 1

    run_event_batch(events, args.outdir, which=args.which,
                     polar_kwargs={"show_tracks": args.show_tracks})
    print(f"Wrote {len(events)} event(s) x {len(args.which)} display(s) to {args.outdir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
