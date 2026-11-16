# Your job: the final check

The shell and every room are built, each by a different agent who saw only its own part. You look at the whole unit the way the person will, find what is wrong or missing, and fix it. After you, the lighting is baked and the model goes to the person, so what you leave is what they get.

1. Run `./unit.sh --check --views plan`. Read the list it prints (doors without handles, rooms without a light, parts overlapping or standing in a wall or in a doorway) and fix every line, in `unit/shell.py` or the room file concerned. Read `unit/shell_issues.md` if it exists and deal with each entry.
2. Compare `unit/renders/plan.png` with `plan.png`: every room there, nothing mirrored, doors where the plan has them.
3. Render every room's views (`VIEWS` in each `unit/room_*.py`; render a few per run) and look at each beside the frames of that room listed in `survey.json`. You are looking for what a builder focused on one room misses: details in close-ups (handles on every door leaf and cabinet front, faucets, hinges, the right number of bulbs on a fixture, switches and outlets), things at the seams between rooms (a counter that should run through an opening, flooring changes at a threshold, the same trim and door colour throughout), light (no dark rooms, no blown-out ones), and source tags (nothing marked `seen` that no frame shows).
4. Fix what you find and render again. Stop when a full pass finds nothing worth the person's notice.

Keep fixes small and in the file that owns the part; do not rewrite a room that is right. Leave `./unit.sh --check` running cleanly. Your final reply: what you fixed, and what is still wrong that you could not fix.
