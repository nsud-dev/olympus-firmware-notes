#!/usr/bin/env python3
"""backdrop.py OUT.rgb [PHOTO | --test] [--png FILE]: a 720 x 480 raw RGB backdrop for om-emu (stands in for live
view; c3drun.mjs BACKDROP, or OM_BACKDROP for session.mjs with patch 0003).
- no argument: a generated landscape (a lake at dusk: sky, sun, hazy ridges, pines, reflections). Made entirely by
  this script, so it carries no third-party licence (MIT with the script).
- PHOTO: that picture, scaled to cover and centre-cropped (record its source, author and licence if you share shots).
- --test: the plain test scene (sky, sun, hills, a checker band) whose hard edges make OSD/IMG2 transparency easy to
  judge.
--png FILE also writes the backdrop as a PNG."""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 720, 480


def test_scene():
    im = Image.new('RGB', (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):                                   # sky: deep blue to warm horizon
        t = y / (H * 0.62); d.line([(0, y), (W, y)], fill=(int(40 + 200 * t), int(90 + 120 * t), int(200 - 60 * t)))
    d.ellipse([500, 70, 600, 170], fill=(255, 226, 120))
    d.polygon([(0, 330), (140, 250), (300, 320), (460, 230), (720, 310), (720, 480), (0, 480)], fill=(60, 120, 60))
    d.polygon([(0, 400), (220, 340), (480, 390), (720, 350), (720, 480), (0, 480)], fill=(35, 85, 40))
    for i in range(0, W, 40):                            # checker band across the lower third
        for j in range(380, 480, 40):
            if (i // 40 + j // 40) % 2: d.rectangle([i, j, i + 39, j + 39], fill=(230, 230, 230))
    return im


def photo(path):
    im = Image.open(path).convert('RGB')
    k = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))


def dusk_lake(W=720, H=480, seed=7, ss=2):
    rng = np.random.default_rng(seed)
    w, h = W*ss, H*ss
    ys = np.linspace(0, 1, h)[:, None]; xs = np.linspace(0, 1, w)[None, :]
    hz = 0.60                                   # horizon (lake line)
    def lerp(a, b, t): return a + (b - a) * t
    def ramp(stops, t):
        t = np.clip(t, 0, 1); out = np.zeros(t.shape + (3,))
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            m = (t >= t0) & (t <= t1); u = ((t - t0) / (t1 - t0))[m][:, None]
            out[m] = lerp(np.array(c0, float), np.array(c1, float), u)
        return out
    sky_t = np.broadcast_to(ys / hz, (h, w))
    sky = ramp([(0, (22, 28, 74)), (0.35, (70, 52, 120)), (0.62, (186, 92, 120)), (0.82, (246, 150, 96)), (1.0, (255, 206, 130))], sky_t)
    sx, sy = 0.66, 0.405
    d = np.sqrt(((xs - sx) * w / h) ** 2 + (ys - sy) ** 2)
    glow = np.exp(-(d / 0.16) ** 2)[..., None] * np.array([255, 190, 110]) * 0.55 + np.exp(-(d / 0.05) ** 2)[..., None] * np.array([255, 230, 170]) * 0.6
    sky = sky + glow
    sky[d < 0.045] = (255, 238, 190)
    # clouds: stretched value noise bands
    def vnoise1(n, octs, s):
        r = np.random.default_rng(s); out = np.zeros(n)
        for o in range(octs):
            k = 4 * 2 ** o; p = r.random(k + 2); x = np.linspace(0, k, n); i = x.astype(int); f = x - i; f = f*f*(3-2*f)
            out += (p[i] * (1 - f) + p[i + 1] * f) / 2 ** o
        return out / 2
    def vnoise2(hh, ww, kx, ky, s):
        r = np.random.default_rng(s); g = r.random((ky + 2, kx + 2))
        img = Image.fromarray((g * 255).astype(np.uint8)).resize((ww, hh), Image.BICUBIC)
        return np.asarray(img, float) / 255
    cl = sum(vnoise2(h, w, 6 * 2**o, 12 * 2**o, seed + o) / 2**o for o in range(4)) / 1.9
    band = np.exp(-((ys - 0.22) / 0.07) ** 2) + 0.7 * np.exp(-((ys - 0.36) / 0.04) ** 2)
    cmask = np.clip((cl - 0.48) * 3.2, 0, 1) * band
    ccol = ramp([(0, (120, 80, 140)), (0.6, (230, 120, 130)), (1, (255, 170, 120))], np.broadcast_to(ys / hz, (h, w)) + 0.15 * (cl - 0.5))
    sky = sky * (1 - cmask[..., None] * 0.8) + ccol * cmask[..., None] * 0.8
    img = sky.copy()
    # ridges far -> near
    layers = [(0.43, 0.08, (150, 110, 160), 0.70, 11), (0.49, 0.10, (100, 78, 130), 0.50, 12), (0.55, 0.09, (60, 52, 96), 0.30, 13), (0.585, 0.05, (34, 36, 66), 0.12, 14)]
    ridge_lines = []
    for base, amp, col, haze, s in layers:
        n = vnoise1(w, 6, s)
        n = n - n.min(); n = n / n.max()
        line = base - amp * (n ** 1.4) * (0.6 + 0.4 * np.sin(np.linspace(0, 3.1, w) + s))
        m = ys >= line[None, :]
        m &= ys < hz
        shade = np.clip((ys - line[None, :]) / 0.12, 0, 1)
        c = np.array(col, float)
        layer = lerp(c * 1.15, c * 0.85, shade[..., None])
        hazecol = np.array([246, 160, 110.]) * haze * np.exp(-((ys - hz) / 0.08) ** 2)[..., None] * 0.6
        layer = np.clip(layer + hazecol * 0.6, 0, 255)
        img[m] = layer[m]
    # trees on the near shore
    tree = np.zeros((h, w), bool)
    r = np.random.default_rng(seed + 99)
    for _ in range(46):
        cx = r.choice([r.uniform(0, 0.28), r.uniform(0.80, 1.0)]); th = r.uniform(0.05, 0.13); tw = th * 0.30 * h / w
        top = hz - th
        yy = np.clip((ys - top) / th, 0, 1)
        jag = 0.75 + 0.25 * np.abs(np.sin(yy * 30))
        tree |= (np.abs(xs - cx) < tw * yy * jag) & (ys > top) & (ys < hz + 0.004)
    img[tree] = (18, 20, 36)
    # lake: mirror above, ripples, darken
    above = img[: int(hz * h)][::-1]
    nlake = h - int(hz * h)
    yl = np.arange(nlake)[:, None]
    ripple = (np.sin(yl * 0.55 + 3 * np.sin(np.arange(w)[None, :] * 0.011)) * (1 + yl / nlake * 4)).astype(int)
    src_y = np.clip(yl + ripple // 3, 0, above.shape[0] - 1)
    src_x = np.clip(np.arange(w)[None, :] + ripple, 0, w - 1)
    lake = above[src_y, src_x]
    lake = lake * np.array([0.62, 0.66, 0.80]) + np.array([4, 8, 20])
    # sun glitter column
    lx = np.arange(w)[None, :] / w
    gl = np.exp(-((lx - sx) / 0.025) ** 2) * (np.random.default_rng(3).random((nlake, w)) > 0.86) * (1 - yl / nlake) ** 0.5
    lake += gl[..., None] * np.array([255, 200, 140]) * 0.8
    lake = lake * (1 - 0.35 * (yl / nlake))[..., None]
    lk = Image.fromarray(np.clip(lake,0,255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.2))
    img[int(hz * h):] = np.asarray(lk, float)
    img[int(hz*h):int(hz*h)+2] *= 0.7
    # foreground shore band
    shore = vnoise1(w, 5, 77); fl = 0.93 - 0.05 * shore
    img[ys >= fl[None, :]] = (14, 16, 28)
    # vignette + grain
    v = 1 - 0.28 * (((xs - 0.5) * 1.6) ** 2 + ((ys - 0.5) * 1.3) ** 2)
    img = img * v[..., None] + rng.normal(0, 2.2, img.shape)
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    return im


if __name__ == '__main__':
    args = sys.argv[1:]
    png = None
    if '--png' in args:
        k = args.index('--png'); png = args[k + 1]; del args[k:k + 2]
    if not args:
        sys.exit(__doc__)
    out, src = args[0], (args[1] if len(args) > 1 else None)
    im = test_scene() if src == '--test' else photo(src) if src else dusk_lake()
    open(out, 'wb').write(im.tobytes())
    if png:
        im.save(png)
