"""VIDEO_VIEWS_V1 (AI Modeling Studio 0.016): turn a turntable video (the object turns once, or the camera circles it)
into a 4-view reference sheet for the normal Image to 3D workflow. Runs in ComfyUI's Python (numpy + PIL).

Usage: python video_views.py spec.json   spec = {"video": path, "ffmpeg": path, "out_dir": folder}
Writes out_dir/sheet.png (front | side A | back | side B in one row, white background), frame_<view>.png (the untouched
video frames that were picked), video_views.json (times, turn length, how each frame was chosen).

How the frames are chosen (no AI):
- frames are sampled at 6 per second (max 100 s); the subject is everything that differs from the border colour;
- the first frame is taken as the FRONT (turntable videos normally start facing the camera - you confirm it at Checkpoint 1);
- one full turn = the later frame whose silhouette best matches the first one (if none matches clearly, the whole video
  is taken as one turn);
- side A / side B = the widest silhouette near 1/4 and 3/4 of the turn; back = the silhouette nearest 1/2 of the turn that
  best matches the mirrored front.
Which side is the creature's LEFT depends on the turning direction and is NOT known: check it at Checkpoint 1."""
import json, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image

VERSION = '0.016'
FPS = 6
MAX_SECONDS = 100
THUMB = 192
NORM = 64


def run(cmd, timeout=240):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError('ffmpeg failed (%s): %s' % (r.returncode, (r.stderr or r.stdout).strip()[-800:]))
    return r


def subject_mask(rgb):
    """Pixels that differ clearly from the border colour (median of the image border)."""
    a = rgb.astype(np.int16); border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    bg = np.median(border, 0); dist = np.abs(a - bg).sum(2)
    return dist > 36, dist, bg


def norm_mask(m):
    ys, xs = np.nonzero(m)
    if len(ys) < 20:
        return None, 0.0
    crop = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    img = Image.fromarray((crop * 255).astype(np.uint8)).resize((NORM, NORM), Image.BILINEAR)
    return np.asarray(img) > 127, float((xs.max() - xs.min() + 1) / m.shape[1])


def pick(masks, widths):
    n = len(masks); m0 = masks[0]
    diff = np.array([np.mean(m0 != m) if m is not None else 1.0 for m in masks])
    period, how = n, 'whole video taken as one turn'
    if n >= 12:
        lo = int(n * 0.6)
        k = lo + int(np.argmin(diff[lo:])) if lo < n else n - 1
        mid = float(np.median(diff[1:])) if n > 2 else 1.0
        if diff[k] < 0.5 * mid:
            period, how = k, 'turn ends at frame %d (silhouette matches the first frame again, difference %.3f vs typical %.3f)' % (k, diff[k], mid)
    win = max(1, period // 10)
    def best(centre, score):
        idx = [i for i in range(max(1, centre - win), min(n - 1, centre + win) + 1) if masks[i] is not None]
        if not idx:
            raise RuntimeError('no usable frame near %d (subject not found against the background)' % centre)
        return max(idx, key=score)
    q1 = best(period // 4, lambda i: widths[i])
    q3 = best(3 * period // 4, lambda i: widths[i])
    mirrored = m0[:, ::-1]
    half = best(period // 2, lambda i: -np.mean(masks[i] != mirrored))
    return {'front': 0, 'side_a': q1, 'back': half, 'side_b': q3}, period, how, diff


def white_background(rgb):
    m, dist, bg = subject_mask(rgb)
    alpha = np.clip((dist - 24) / 36.0, 0, 1)[..., None]
    out = rgb.astype(np.float32) * alpha + 255.0 * (1 - alpha)
    return out.astype(np.uint8), m


def panel(rgb, size=720):
    img, m = white_background(rgb)
    ys, xs = np.nonzero(m)
    if len(ys) < 50:
        raise RuntimeError('subject not found in a picked frame')
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    side = max(xs.max() - xs.min(), ys.max() - ys.min()) * 1.18
    box = (int(cx - side / 2), int(cy - side / 2), int(cx + side / 2), int(cy + side / 2))
    canvas = Image.new('RGB', (box[2] - box[0], box[3] - box[1]), (255, 255, 255))
    src = Image.fromarray(img); canvas.paste(src, (-box[0], -box[1]))
    return canvas.resize((size, size), Image.LANCZOS)


def main(spec):
    video, ffmpeg, out = Path(spec['video']), spec['ffmpeg'], Path(spec['out_dir'])
    out.mkdir(parents=True, exist_ok=True); thumbs = out / 'thumbs'; thumbs.mkdir(exist_ok=True)
    run([ffmpeg, '-v', 'error', '-y', '-i', video, '-t', MAX_SECONDS, '-vf', 'fps=%d,scale=%d:-2' % (FPS, THUMB), thumbs / 't_%04d.png'])
    files = sorted(thumbs.glob('t_*.png'))
    if len(files) < 8:
        raise RuntimeError('the video is too short: %d frames at %d per second (need at least about 2 seconds of one full turn)' % (len(files), FPS))
    masks, widths = [], []
    for f in files:
        m, _, _ = subject_mask(np.asarray(Image.open(f).convert('RGB')))
        nm, w = norm_mask(m); masks.append(nm); widths.append(w)
    if masks[0] is None:
        raise RuntimeError('the subject was not found in the first frame (it must stand out from a plain background)')
    picks, period, how, diff = pick(masks, widths)
    frames, rows = {}, {}
    for view, i in picks.items():
        t = i / FPS; p = out / ('frame_%s.png' % view)
        run([ffmpeg, '-v', 'error', '-y', '-ss', '%.3f' % t, '-i', video, '-frames:v', '1', p])
        frames[view] = np.asarray(Image.open(p).convert('RGB')); rows[view] = {'frame_index': i, 'time_s': round(t, 3), 'silhouette_width': round(widths[i], 3), 'file': p.name}
    gap, size = 60, 720
    sheet = Image.new('RGB', (4 * size + 5 * gap, size + 2 * gap), (255, 255, 255))
    for k, view in enumerate(('front', 'side_a', 'back', 'side_b')):
        sheet.paste(panel(frames[view], size), (gap + k * (size + gap), gap))
    sheet.save(out / 'sheet.png')
    info = {'version': VERSION, 'video': video.name, 'sampled_fps': FPS, 'frames_sampled': len(files), 'turn_frames': period, 'turn_seconds': round(period / FPS, 2),
            'turn_detection': how, 'views': rows, 'sheet': 'sheet.png', 'layout': 'one row: front | side A | back | side B',
            'limits': ['front = first frame of the video (check it)', 'which side is LEFT is not known - check left/right at Checkpoint 1',
                       'background removed by colour difference to the border; Checkpoint 1 background removal decides the final outline']}
    (out / 'video_views.json').write_text(json.dumps(info, indent=1), encoding='utf-8')
    for f in files:
        f.unlink()
    thumbs.rmdir()
    print('VIDEO_VIEWS_PASSED', json.dumps({k: v['time_s'] for k, v in rows.items()}), flush=True)


if __name__ == '__main__':
    main(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
