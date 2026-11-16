# Your job: the survey

You go first. You study the plan and every frame and write `survey.json`, which the builders after you rely on instead of studying everything again themselves, and which decides whether the person is asked for more photos. You do not model anything.

Work through these in order:

1. **The plan.** Read every label. List the rooms, closets and other spaces, and which printed dimension belongs to which.
2. **Scale.** If the plan has printed dimensions, derive inches per pixel of `plan.png` from several of them and say how well they agree (`"method": "labels"`). If it has none, estimate it from the drawing itself (`"method": "pixels"`): measure, in pixels, things whose real size is known, such as door openings and their swing arcs (a swing radius is the leaf width, usually 30 in; entry doors 36 in), tubs (60 in), toilets, kitchen counter depth (25 in), a range or refrigerator (30 in), beds if drawn, wall thickness (interior about 4.5 in). Use at least four different kinds of reference, discard outliers, take the median, and then sanity-check the result against the frames: do the rooms come out at believable sizes, does the ceiling-to-door proportion fit? Record every reference you used in `"basis"`.
3. **Orientation.** Decide from the frames whether the real unit is as drawn or mirrored. Follow the camera from the entry: which side is the kitchen on, which way do doors swing, where are the windows? Give the evidence.
4. **Rooms.** For each space give its name (lower-case, letters, digits and underscores only: `living`, `kitchen`, `bedroom_1`, `bath`, `hall_closet`), its rectangle in the shared coordinate frame (interior faces, inches; an L-shaped room is its bounding rectangle, with the shape noted in `contents`), its region on `plan.png` in pixels, the frames that show it best (at most eight, most useful first), and what is in it, wall by wall (north, east, south, west as on the plan after mirroring): openings, cabinets and appliances in order along the wall, fixtures, finishes, anything on the walls and ceiling, and furniture if the person asked for furniture. An open kitchen and living room are two spaces if the plan labels them separately. Rate coverage: `full` (every wall and its contents can be seen), `partial`, or `none`.
5. **Finishes that run through the whole unit**, measured, not guessed: sample wall paint, flooring, trim, doors and cabinet fronts from several frames with Python (median of a patch away from highlights and shadows) and give sRGB values. A camera's exposure and white balance make every sample darker and warmer than the surface really is, and the model's lighting darkens it a second time, so correct for it: find something in the same frames that is really white (ceiling, trim, a white door or appliance), work out the per-channel factor that brings its sample to about 240, and apply that factor to every other sample. Report the corrected values; say which way floor boards run (`u` along x, `v` along y), the ceiling height (estimate it against a door leaf if the plan does not say), and the hardware finish.
6. **Gaps.** A gap is something the builders cannot build faithfully without another photo: a room, or a wall that holds fixtures, cabinets or openings, that no frame shows. Ask only for what would change the model: a blank stretch of wall, the inside of a closet, or a ceiling are not worth the person's time, and are simply guessed. At most five, most important first. For each say exactly what to photograph and from where, in plain words a person standing in the unit can follow ("the bathroom from the doorway, so the vanity and the tub are both in the picture").

`survey.json`:

```json
{
  "scale": {"method": "labels|pixels", "inches_per_px": 0.0, "basis": "which labels or references, and how well they agree", "confidence": "high|medium|low"},
  "mirrored_vs_plan": false,
  "orientation_evidence": "one or two sentences",
  "footprint_in": {"width": 0, "depth": 0},
  "ceiling_in": 96,
  "furniture_present": true,
  "finishes": {"wall_rgb": [0, 0, 0], "ceiling_rgb": [0, 0, 0], "trim_rgb": [0, 0, 0], "door_rgb": [0, 0, 0],
               "floor": {"key": "floor_wood|floor_tile|carpet|concrete", "rgb": [0, 0, 0], "plank": "u|v"}, "hardware": "black_metal|chrome|nickel|brass"},
  "rooms": [{"name": "", "kind": "living|kitchen|bedroom|bath|closet|laundry|hall|entry|other", "label_dims": "as printed, or null",
             "rect_in": [0, 0, 0, 0], "plan_px": [0, 0, 0, 0], "coverage": "full|partial|none", "frames": ["frames/..."],
             "contents": "wall by wall", "unseen": "what no frame shows"}],
  "gaps": [{"id": "g1", "room": "", "plan_px": [0, 0, 0, 0], "ask": "what to photograph, from where", "why": "what it would change"}],
  "notes": "anything the builders should know"
}
```

`rect_in` is `[x0, x1, y0, y1]`; `plan_px` is `[x, y, width, height]` on `plan.png` as uploaded (not mirrored). Before you finish, check that the room rectangles tile the footprint without overlapping, that printed dimensions are reproduced exactly, and that the file parses. Your final reply is two or three sentences: scale method and confidence, orientation, and how many gaps.
