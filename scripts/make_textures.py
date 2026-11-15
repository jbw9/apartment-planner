"""Generates the tiling finish textures and the window backdrop into public/tex.
usage: python3 make_textures.py <video> <outdir>"""
import sys, subprocess, numpy as np, cv2
video, out = sys.argv[1], sys.argv[2]
rng = np.random.default_rng(7)

def fbm(h, w, sy, sx, octaves=5):
    """Anisotropic value noise in [0,1]; sy/sx = feature size in px of the first octave."""
    acc = np.zeros((h, w), np.float32); amp = 1.0; tot = 0
    for o in range(octaves):
        gh, gw = max(2, int(h / sy * 2 ** o) + 2), max(2, int(w / sx * 2 ** o) + 2)
        n = rng.random((gh, gw), dtype=np.float32)
        acc += amp * cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC); tot += amp; amp *= 0.5
    return acc / tot

# ---- floor: 7" x 48" vinyl planks, 16 planks x 3 lengths => 112" x 144"
PPI = 32
W, H = 112 * PPI, 144 * PPI
pw, pl = 7 * PPI, 48 * PPI
img = np.zeros((H, W, 3), np.float32)
rough = np.zeros((H, W), np.float32)
palette = np.array([[214, 203, 184], [200, 184, 158], [187, 166, 134], [207, 194, 172], [181, 159, 127], [218, 209, 193]], np.float32)
joints = np.zeros((H, W), np.float32)
for c in range(16):
    off = int(rng.integers(0, pl))
    x0 = c * pw
    for r in range(-1, 4):
        y0, y1 = max(0, r * pl + off), min(H, (r + 1) * pl + off)
        if y1 <= y0: continue
        a, b = rng.choice(len(palette), 2, replace=False)
        base = palette[a] * 0.75 + palette[b] * 0.25
        hh = y1 - y0
        g = fbm(hh, pw, 900, 5, 4)                       # long fibres
        g2 = fbm(hh, pw, 260, 26, 3)                     # cathedral figure
        g3 = fbm(hh, pw, 2400, 60, 2)
        t = (g - 0.5) * 0.09 + (np.sin(g2 * 28) * 0.5) * 0.03 + (g3 - 0.5) * 0.07
        img[y0:y1, x0:x0 + pw] = base[None, None, :] * (1 + t[..., None])
        rough[y0:y1, x0:x0 + pw] = 0.42 + (g - 0.5) * 0.25
        if 0 < y0 < H: joints[y0 - 1:y0 + 1, x0:x0 + pw] = 1
    joints[:, x0:x0 + 2] = 1
joints = cv2.GaussianBlur(joints, (0, 0), 0.8)
img *= (1 - 0.3 * joints[..., None])
rough = np.clip(rough + joints * 0.3, 0, 1)
cv2.imwrite(f"{out}/floor_color.jpg", cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
cv2.imwrite(f"{out}/floor_rough.jpg", (rough * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 88])
hgt = cv2.GaussianBlur(1 - joints, (0, 0), 1.2) + (fbm(H, W, 600, 4, 3) - 0.5) * 0.05
gx = cv2.Sobel(hgt, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(hgt, cv2.CV_32F, 0, 1, ksize=3)
nrm = np.dstack([-gx * 2.0, gy * 2.0, np.ones_like(gx)]); nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
cv2.imwrite(f"{out}/floor_normal.jpg", cv2.cvtColor(((nrm * 0.5 + 0.5) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])

# ---- cabinet wood: pale ash laminate, vertical grain, 24" x 24"
S_ = 1024
g = fbm(S_, S_, 700, 4, 4); g2 = fbm(S_, S_, 300, 40, 3)
t = (g - 0.5) * 0.13 + (g2 - 0.5) * 0.10
wood = np.array([226, 217, 202], np.float32)[None, None] * (1 + t[..., None])
wood[..., 2] *= 1 - (g2 - 0.5) * 0.06
cv2.imwrite(f"{out}/cab_wood.jpg", cv2.cvtColor(np.clip(wood, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])

# ---- marble-look backsplash: 4" x 16" tiles, third-offset, 48" x 24"
TP = 40
TW, TH = 48 * TP, 24 * TP
tile = np.zeros((TH, TW, 3), np.float32); tj = np.zeros((TH, TW), np.float32)
big = fbm(TH * 3, TW * 3, 500, 900, 5)
for r in range(6):
    y0 = r * 4 * TP
    shift = (r % 3) * (16 * TP) // 3
    for c in range(-1, 4):
        x0 = c * 16 * TP + shift
        a, b = max(0, x0), min(TW, x0 + 16 * TP)
        if b <= a: continue
        oy, ox = int(rng.integers(0, TH * 2)), int(rng.integers(0, TW * 2))
        n = big[oy:oy + 4 * TP, ox:ox + (b - a)]
        vein = np.clip(1 - np.abs(n - 0.5) * 22, 0, 1) ** 2
        soft = (big[oy // 2:oy // 2 + 4 * TP, ox // 2:ox // 2 + (b - a)] - 0.5)
        col = 238 - vein * 46 + soft * 26
        tile[y0:y0 + 4 * TP, a:b] = np.dstack([col * 0.995, col, col * 1.012])
        if a > 0: tj[y0:y0 + 4 * TP, a - 1:a + 2] = 1
    tj[y0:y0 + 3, :] = 1
tj = cv2.GaussianBlur(tj, (0, 0), 1.0)
tile *= (1 - 0.3 * tj[..., None])
cv2.imwrite(f"{out}/tile_marble.jpg", cv2.cvtColor(np.clip(tile, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])

# ---- brushed stainless roughness streaks + wall micro texture
b = fbm(512, 512, 4, 700, 3)
cv2.imwrite(f"{out}/brushed.jpg", (np.clip(0.5 + (b - 0.5) * 0.9, 0, 1) * 255).astype(np.uint8))
w = fbm(512, 512, 5, 5, 3)
hx = cv2.Sobel(w, cv2.CV_32F, 1, 0); hy = cv2.Sobel(w, cv2.CV_32F, 0, 1)
n = np.dstack([-hx * 0.35, hy * 0.35, np.ones_like(hx)]); n /= np.linalg.norm(n, axis=2, keepdims=True)
cv2.imwrite(f"{out}/wall_normal.jpg", cv2.cvtColor(((n * 0.5 + 0.5) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])

# ---- outdoor backdrop from the walkthrough video (view above the balcony railing)
def frame(t):
    p = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", video, "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(p, np.uint8), cv2.IMREAD_COLOR)
L, R = frame(53.5), frame(49.5)
h = int(L.shape[0] * 0.56)
L, R = L[:h].astype(np.float32), R[:h].astype(np.float32)
ov = 160
ramp = np.linspace(0, 1, ov, dtype=np.float32)[None, :, None]
pano = np.hstack([L[:, :-ov], L[:, -ov:] * (1 - ramp) + R[:, :ov] * ramp, R[:, ov:]])
pano = np.hstack([pano, pano[:, ::-1]])      # mirror so the strip wraps without a seam
cv2.imwrite(f"{out}/backdrop.jpg", np.clip(pano, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 90])
print("textures done", pano.shape)
