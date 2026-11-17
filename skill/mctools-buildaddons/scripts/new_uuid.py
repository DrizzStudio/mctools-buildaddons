#!/usr/bin/env python3
"""Generate fresh random (v4) UUIDs for Minecraft Bedrock manifest.json files.

Never type UUIDs by hand and never reuse the example UUIDs from tutorials:
Minecraft silently refuses to load a pack whose UUID collides with another pack.

Usage:
  python new_uuid.py                 # one UUID
  python new_uuid.py -n 5            # five UUIDs
  python new_uuid.py --labels bp_header,bp_data,bp_script,rp_header,rp_resources
"""
import argparse
import uuid


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-n", type=int, default=1, help="how many UUIDs to print")
    parser.add_argument("--labels", help="comma separated labels; prints 'label: uuid' lines")
    args = parser.parse_args()

    if args.labels:
        for label in [x.strip() for x in args.labels.split(",") if x.strip()]:
            print(f"{label}: {uuid.uuid4()}")
        return

    for _ in range(max(1, args.n)):
        print(uuid.uuid4())


if __name__ == "__main__":
    main()
