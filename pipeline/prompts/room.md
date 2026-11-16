# Your job: one room

The shell of the unit (walls, floor, ceiling, doors, windows, daylight) is built. You fill one room with everything that is in it. Other agents are doing the other rooms at the same time.

Read your room's survey entry in the job message, `unit/layout.json` (the shell's exact walls, rooms and openings; build against these numbers, not the survey's estimates), and `kit_api.md` (the parts kit: `kit.core` in full, then the modules your kind of room needs). Then look at the frames listed for your room and write `unit/room_<name>.py`:

```python
from kit import core, kitchen, bath, fixtures, furniture   # what you need

def build(s):          # s is the Shell; place parts, do not build walls
    ...

VIEWS = {"<name>_1": ((x, y, 63), (x, y, 40)), ...}   # two to four eye-level views that show the room well
```

What belongs in it, where the frames show it:

- Kitchen: cabinet runs with the right segments in the right order (doors, drawers, sink, dishwasher, range, refrigerator, microwave or hood, open shelves), counters, backsplash, appliance and hardware finishes.
- Bathroom: tub or shower with its surround, toilet, vanity, mirror, vanity light, towel bars, paper holder.
- Laundry and closets: washer and dryer, water heater, shelves and rods, panels.
- Every room: ceiling lights at their real positions (every room needs at least one light fixture, or it bakes dark), vents, smoke detectors, thermostat, switches by the doors, outlets.
- Furniture and loose items only if the job message says so; then every piece the frames show, at its real size, position and colour.

How to work:

1. Establish which wall is which. Match two or three things in a frame (a window, a door, the next room seen through an opening) to `layout.json` before placing anything; a room built mirrored is the most common mistake.
2. Take sizes from the frames against known ones (a door leaf is 80 in tall; a counter is 36 in high; cabinet doors are usually 12 to 18 in wide each) and colours by sampling the frames with Python (median of a patch away from highlights and shadows), not by eye. Correct each sample for the camera's exposure the way the survey did: scale it by the factor that brings a really white surface in the same frame (ceiling, trim) to about 240, or the room comes out darker and yellower than it is.
3. Use the kit's parts and their options; they are tested and already carry their handles, hardware and collision footprints. Only when the kit has nothing close, build the item from `kit.core` primitives in a small function in your file, using the material keys in `kit_api.md` and nothing else, inside `with core.tag(group="C")` (built-in) or `group="D"` (furniture), and call `core.footprint` for anything standing on the floor.
4. Tag what you could not see: pass `source="plan"` or `source="guess"` to those parts (or wrap several in `with core.tag(source="guess"):`). If your room's coverage is `none`, the whole room is a guess: furnish it as such a room in such a unit normally is, modestly.
5. Check as you go: `./unit.sh --only <name> --check --views <view>,<view>` builds the shell plus your room only and renders previews into `unit/renders/` in a few seconds. Put each render beside the frame that shows the same wall in one image, and list the differences: position and size, missing or wrong items, colour and finish. Fix and repeat while a pass still finds something. Look for the kit's own failure signs too: a part facing the wall, floating above or sunk into the floor, baseboard running across a cabinet front, a door that cannot open because something stands in its swing.

Edit only your own file. If the shell is wrong for your room (a door on the wrong wall, a missing window), do not work around it silently: append a line saying what and why to `unit/shell_issues.md` and build as if it were fixed where you can.

Your final reply: what you placed, what is a guess, and what you could not match.
