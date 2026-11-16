# Your job: the shell

You build the empty unit that every room builder then works inside: walls, floors, ceilings, doors and windows, and daylight. Their work is only as right as your walls, and they cannot move them, so dimensions and openings matter more than anything else here.

Read `survey.json` (the surveyor's findings: scale, orientation, rooms, finishes, which frames show what) and `kit_api.md` (the parts kit; read the `kit.core`, `kit.shell`, `kit.openings` and `kit.lights` sections in full). Then write `unit/shell.py`:

```python
from kit import lights
from kit.shell import Shell
from kit.openings import door, window

def build():
    s = Shell(96, wall_rgb=..., floor="floor_wood", floor_rgb=..., plank="v")
    s.wall(...); s.room(...)            # every wall and every space
    door(s, ...); w = window(s, ...)    # every door and window
    lights.daylight(sun_from="S"); lights.portal(w, s)
    return s                            # do not call s.build(); the runner does, after the rooms are filled
```

What it must contain:

- Every room, closet and other space in the survey, under exactly the survey's names (room builders are started by name), with walls of real thickness (exterior about 8 in, interior 4.5 in, plumbing walls 6.5 in). An L-shaped room is several `s.room()` rectangles with one name. Printed dimensions are exact; the survey's rectangles are estimates you should refine against the plan and the frames.
- Every door, with the swing side, hinge side and kind (hinged, double, bypass, bifold, or a plain cased opening) the frames show, the right handle type and finish, and the entry door's deadbolt and peephole. Leave interior doors open (`angle` 80 to 90) so the rooms can be seen and walked into; the entry door closed.
- Every window and glazed door at its real width, sill height and head height, with the right style and whether it has blinds.
- Lowered ceilings and soffits, knee walls and half walls, and each room's flooring where it differs from the unit's.
- Daylight, and a portal for each window. Put the sun on the side the main room's windows face (`sun_from`), at 35 to 45 degrees, so that sunlight falls into the unit: the person can dim it in the viewer, but a unit with no direct sun looks flat. Leave blinds raised (the default) even if the frames show them lowered, for the same reason.
- Source tags: pass `source="plan"` or `source="guess"` for walls, rooms, doors and windows that no frame shows.

Use only kit parts and the material keys in `kit_api.md`; the viewer has a tuned material for each of those and nothing else. If the kit truly has no part for something in the shell, build it from `kit.core` primitives in a small function in `shell.py`.

How to check your work: `./unit.sh --check --views plan` builds the shell and renders `unit/renders/plan.png`, a top view with the ceiling off, and writes `unit/layout.json`. Put that render beside `plan.png` (mirrored if the unit is) in one image and compare room by room: proportions, door positions and swings, window positions. Then add a `VIEWS = {"name": ((x, y, z), (x, y, z))}` dictionary (eye and target, eye height 63) with one view per main room looking at its windows or doors, render them with `./unit.sh --views name,name`, and compare each with a frame taken from a similar spot: are the openings where the frame shows them, at the right size? Fix and repeat until a pass finds nothing. Measure the room sizes from `layout.json` and confirm that every printed dimension is reproduced.

Leave `shell.py` importable and `./unit.sh --check --views plan` running cleanly. Your final reply: the room sizes, what you were unsure about, and anything the room builders should know.
