"""Single source of truth for the apartment's dimensions. All values in inches.

Axes: U runs across the unit (0 = bedroom exterior wall, increasing toward the kitchen wall),
V runs from the window wall toward the entry door, Z is up from the finished floor.
The built unit is the mirror image of the marketing floor plan (kitchen on the right as you enter).

The four dimensions printed on the plan are exact: Living 11'4" x 12'9", Bedroom 10'9" x 12'4".
Everything the plan does not label comes from the drawing's scale and the walkthrough video.
The drawing is not to scale with its own labels, so the bedroom's exterior wall (U0) and the
window wall (V0) sit outside the drawing's 0 lines to make the labelled rooms come out exact.
"""

U0 = -13.0   # bedroom exterior wall: bedroom is U0..116 = 129" (10'9")
V0 = -18.0   # window wall: living is V0..135 = 153" (12'9"), bedroom V0..130 = 148" (12'4")

CEIL = 108.0
SLAB = 8.0

# (u0, u1, v0, v1, z0, z1)
WALLS = [
    # exterior
    (U0 - 10, 267.5, V0 - 10, V0, 0, CEIL),  # window wall
    (U0 - 10, U0, V0 - 10, 140.5, 0, CEIL),  # bedroom side exterior
    (U0 - 10, 30, 130, 140.5, 0, CEIL),     # exterior jog behind bedroom
    (20, 30, 130, 405.5, 0, CEIL),          # closet / bath exterior
    (20, 228, 395, 405.5, 0, CEIL),         # corridor (entry) wall
    (30, 80, 353, 395, 0, CEIL),            # chase next to washer/dryer
    (217.5, 228, 307, 405.5, 0, CEIL),      # coat closet back
    (217.5, 267.5, 307, 317.5, 0, CEIL),    # kitchen end wall
    (257.5, 267.5, V0 - 10, 317.5, 0, CEIL),  # kitchen side exterior
    # interior partitions
    (116, 121.5, V0, 395, 0, CEIL),         # living | bedroom, closet, bath
    (U0, 116, 130, 135.5, 0, CEIL),         # bedroom | walk-in closet
    (30, 116, 224, 229, 0, CEIL),           # walk-in closet | bath
    (30, 56, 229, 265, 0, CEIL),            # chase at tub end
    (187.5, 192.5, 307, 395, 0, CEIL),      # coat closet front
    (187.5, 228, 307, 312.5, 0, CEIL),      # coat closet end / behind fridge
]

# name -> box carved out of the walls
OPENINGS = {
    "slider":        (135, 231, V0 - 10, V0, 0, 92),
    "bed_window":    (26, 66, V0 - 10, V0, 14, 102),
    "bed_door":      (116, 121.5, 94, 126, 0, 81),
    "bath_door":     (116, 121.5, 316, 348, 0, 81),
    "closet_door":   (38.5, 70.5, 130, 135.5, 0, 81),
    "entry_door":    (128.5, 164.5, 395, 405.5, 0, 81),
    "coat_closet":   (187.5, 192.5, 320, 379, 0, 81),
}
# openings you can walk through (used for collision + floor finish)
PASSABLE = ["bed_door", "bath_door", "closet_door", "coat_closet"]

# dropped ceilings / soffits
CEILINGS = [
    (U0 - 10, 267.5, V0 - 10, 405.5, CEIL, CEIL + SLAB),   # main slab
    (231.5, 257.5, 127, 307, 96, CEIL),            # kitchen soffit
    (121.5, 231.5, 312, 395, 96, CEIL),            # entry hall drop
    (192.5, 217.5, 312.5, 395, 96, CEIL),          # coat closet
    (100, 116, V0, 130, 92, CEIL),                  # bedroom soffit
    (30, 116, 229, 395, 96, CEIL),                 # bathroom drop
]

# name -> (u0, u1, v0, v1) interior clear floor area
ROOMS = {
    "Living":   (121.5, 257.5, V0, 135),
    "Kitchen":  (121.5, 257.5, 135, 307),
    "Entry":    (121.5, 187.5, 307, 395),
    "Coat closet": (192.5, 217.5, 312.5, 395),
    "Bedroom":  (U0, 116, V0, 130),
    "Closet":   (30, 116, 135.5, 224),
    "Bath":     (30, 116, 229, 353),
    "Laundry":  (80, 116, 353, 395),
}

# fixed things furniture can't overlap: name -> (u0, u1, v0, v1, height)
FIXTURES = {
    "Kitchen counter": (232, 257.5, 135, 270, 36),
    "Refrigerator":    (227, 257.5, 270, 307, 96),
    "Bathtub":         (56, 116, 229, 261, 20),
    "Toilet":          (30, 58, 273, 293, 30),
    "Vanity":          (30, 51.5, 304, 353, 36),
    "Washer / dryer":  (82, 114, 357, 395, 78),
}

# door leaves as modelled (hinge u, hinge v, width, closed direction, open direction) for plan drawing
DOOR_SWINGS = [
    {"name": "bed_door",    "hinge": (116, 126),    "w": 32, "closed": (0, -1), "open": (-1, 0)},
    {"name": "bath_door",   "hinge": (116, 348),    "w": 32, "closed": (0, -1), "open": (-1, 0)},
    {"name": "closet_door", "hinge": (38.5, 135.5), "w": 32, "closed": (1, 0),  "open": (0, 1)},
    {"name": "entry_door",  "hinge": (128.5, 395),  "w": 36, "closed": (1, 0),  "open": (0, -1)},
]

# kitchen run along the U=257.5 wall, measured along V
K0 = 135.0
KITCHEN = {
    "drawers": (135, 153), "sink": (153, 189), "dw": (189, 213), "cab_a": (213, 228),
    "range": (228, 258), "cab_b": (258, 270), "fridge": (270, 307),
}

# recessed / surface lights: (u, v, z, radius, kind)
LIGHTS = [
    (222, 158, CEIL, 3.0, "can"), (222, 214, CEIL, 3.0, "can"), (222, 270, CEIL, 3.0, "can"),
    (154, 334, 96, 3.0, "can"), (154, 374, 96, 3.0, "can"),
    (51.5, 56, CEIL, 5.5, "disc"),
    (73, 190, CEIL, 3.0, "can"),
    (76, 300, 96, 3.0, "can"),
]
