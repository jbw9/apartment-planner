"""Edge-preserving denoise of the baked lightmaps (EXR in -> half-float EXR out).
usage: python3 denoise_lightmaps.py <bake dir> <out dir>"""
import os, sys
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
import cv2, numpy as np
src, dst = sys.argv[1], sys.argv[2]
for name in ("lm_A_day", "lm_A_lamp", "lm_B_day", "lm_B_lamp"):
    img = cv2.imread(f"{src}/{name}.exr", cv2.IMREAD_UNCHANGED)[:, :, :3].astype(np.float32)
    img = np.nan_to_num(np.clip(img, 0, 64))
    mask = (img.sum(axis=2) > 0).astype(np.float32)
    lg = np.log1p(img * 8.0)
    for _ in range(2):                       # bilateral in log space keeps sun-patch and contact edges
        lg = cv2.bilateralFilter(lg, 9, 0.22, 2.6)
    # normalised so unbaked (black) texels between islands never darken island borders
    k = cv2.GaussianBlur(mask, (0, 0), 1.0)
    sm = cv2.GaussianBlur(lg * mask[..., None], (0, 0), 1.0) / np.maximum(k, 1e-4)[..., None]
    out = np.expm1(np.where(mask[..., None] > 0, sm, lg)) / 8.0
    cv2.imwrite(f"{dst}/{name}.exr", out.astype(np.float32),
                [cv2.IMWRITE_EXR_TYPE, cv2.IMWRITE_EXR_TYPE_HALF, cv2.IMWRITE_EXR_COMPRESSION, cv2.IMWRITE_EXR_COMPRESSION_ZIP])
    print(name, img.shape, "max", float(out.max()))
