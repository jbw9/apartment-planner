#!/usr/bin/env python3
"""Runs one job's stages. A job is a directory:

    job.json      {"title": "...", "furniture": true}
    inputs/       plan.<png|jpg|pdf> and the photos and videos, as uploaded
    answers.json  {"<gap id>": "guess" | "provided"}   (follow-up files go in inputs/ too, named <gap id>_*)

usage: stages.py <job-dir> ingest|survey|build|bake|all
Needs BLENDER (path to the blender binary) and AWS credentials for Bedrock; APT_MODEL overrides the model."""
import ast
import glob
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

import agent

HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.dirname(HERE)
MODEL = os.environ["APT_MODEL"]   # Bedrock model id or inference profile ARN
BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
SLOTS = int(os.environ.get("BLENDER_SLOTS", "2"))   # Blender runs allowed at once; more than the GPU's memory holds fails
JOB_CAP = float(os.environ.get("APT_JOB_CAP", "25"))
# dollars each agent may spend; a job that hits its cap stops rather than runs on
BUDGET = {"survey": 3.0, "shell": 5.0, "room": 3.0, "check": 4.0}
EFFORT = {"survey": "high", "shell": "high", "room": "medium", "check": "medium"}
VIDEO, IMAGE = (".mp4", ".mov", ".m4v", ".webm"), (".jpg", ".jpeg", ".png", ".heic", ".webp")


def prompt(name):
    return open(os.path.join(PIPE, "prompts", name + ".md")).read()


def metrics(job, stage=None, **kw):
    p = os.path.join(job, "metrics.json")
    m = json.load(open(p)) if os.path.exists(p) else {}
    if stage:
        m[stage] = {**m.get(stage, {}), **kw}
        json.dump(m, open(p, "w"), indent=1)
    return m


def spent(job):
    return sum(v.get("usd", 0) for v in metrics(job).values())


def run_agent(job, name, kind, message):
    left = JOB_CAP - spent(job)
    if left <= 0.5:
        raise SystemExit("job cost cap reached before " + name)
    system = prompt("common") + "\n\n" + prompt(kind)
    s = agent.run(os.path.join(job, "runs", name), job, MODEL, system, message, EFFORT[kind], min(BUDGET[kind], left))
    metrics(job, name, minutes=s["minutes"], usd=s["cost_usd"], turns=s["turns"], status=s["status"])
    return s


# ------------------------------------------------------------------ ingest
def ingest(job):
    """Turns whatever was uploaded into things an agent can look at cheaply: a plan image, one frame a second from
    each video, and contact sheets of every frame and photo."""
    t0 = time.time()
    inp, frames, sheets = (os.path.join(job, d) for d in ("inputs", "frames", "sheets"))
    os.makedirs(frames, exist_ok=True)
    os.makedirs(sheets, exist_ok=True)
    for f in sorted(f for f in os.listdir(inp) if not f.startswith(".")):
        stem, ext = os.path.splitext(f)
        src, ext = os.path.join(inp, f), ext.lower()
        if stem.startswith("plan"):   # plan.png, and plan_2.png ... when more than one drawing was uploaded
            if ext == ".pdf":
                subprocess.run(["pdftoppm", "-png", "-r", "200", "-singlefile", src, os.path.join(job, stem)], check=True)
            else:
                cv2.imwrite(os.path.join(job, stem + ".png"), cv2.imread(src))
        elif ext in VIDEO and not glob.glob(os.path.join(frames, stem + "_*.jpg")):
            subprocess.run(["ffmpeg", "-loglevel", "error", "-i", src, "-vf", "fps=1,scale=1280:-2", "-q:v", "3",
                            os.path.join(frames, stem + "_%04d.jpg")], check=True)
        elif ext in IMAGE and not os.path.exists(os.path.join(frames, stem + ".jpg")):
            tmp = src
            if ext == ".heic":   # OpenCV cannot read HEIC; ffmpeg can
                tmp = os.path.join(frames, stem + ".tmp.png")
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, tmp], check=True)
            im = cv2.imread(tmp)
            k = 1568 / max(im.shape[:2])
            cv2.imwrite(os.path.join(frames, stem + ".jpg"), cv2.resize(im, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else im)
            if tmp != src:
                os.remove(tmp)
    names = sorted(f for f in os.listdir(frames) if f.endswith(".jpg") and not f.startswith("."))
    for old in glob.glob(os.path.join(sheets, "*.jpg")):
        os.remove(old)
    W, H, COLS, ROWS = 384, 240, 5, 4
    for i in range(0, len(names), COLS * ROWS):
        sheet = np.full((ROWS * H, COLS * W, 3), 24, np.uint8)
        for j, n in enumerate(names[i:i + COLS * ROWS]):
            im = cv2.imread(os.path.join(frames, n))
            k = min(W / im.shape[1], (H - 22) / im.shape[0])
            im = cv2.resize(im, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
            y, x = (j // COLS) * H, (j % COLS) * W
            sheet[y + 22:y + 22 + im.shape[0], x:x + im.shape[1]] = im
            cv2.putText(sheet, n[:-4], (x + 4, y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imwrite(os.path.join(sheets, "sheet_%02d.jpg" % (i // (COLS * ROWS) + 1)), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    metrics(job, "ingest", minutes=round((time.time() - t0) / 60, 1), usd=0, frames=len(names))


# ------------------------------------------------------------------ survey
def survey(job):
    cfg = json.load(open(os.path.join(job, "job.json")))
    ans_p = os.path.join(job, "answers.json")
    if os.path.exists(os.path.join(job, "survey.json")):
        if not os.path.exists(ans_p) or "survey2" in metrics(job):
            return
        sv, ans = json.load(open(os.path.join(job, "survey.json"))), json.load(open(ans_p))
        if all(ans.get(g["id"], "guess") == "guess" for g in sv.get("gaps", [])):   # nothing new to look at
            for g in sv.get("gaps", []):
                g["answer"] = "guess"
            json.dump(sv, open(os.path.join(job, "survey.json"), "w"), indent=1)
            return metrics(job, "survey2", minutes=0, usd=0)
        # second pass, after the user answered: only the rooms that had a gap are looked at again
        msg = ("The user has answered your questions; the answers are in answers.json (\"provided\" means new files, whose frames are in "
               "frames/ named <gap id>_*, and sheets/ has been rebuilt; \"guess\" means they cannot supply it). Update survey.json: for "
               "each gap add \"answer\", add the new frames to the room's \"frames\", revise that room's \"contents\", \"unseen\" and "
               "\"coverage\" from what the new frames show. Leave every other room as it is. Do not ask further questions.")
        return run_agent(job, "survey2", "survey", msg)
    msg = ("Working directory: %s\nThe floor plan is plan.png. Frames and photos are in frames/ (%d files), with contact sheets of all "
           "of them in sheets/. The original uploads are in inputs/ if you need a full-resolution still (ffmpeg is installed).\n"
           "The user %s. Write survey.json." % (job, len(glob.glob(os.path.join(job, "frames", "*.jpg"))),
                                                "wants the furniture in the photos modelled" if cfg.get("furniture") else "wants the unit modelled empty, without furniture"))
    return run_agent(job, "survey", "survey", msg)


# ------------------------------------------------------------------ build
def api_doc():
    """The kit's public functions with their docstrings, as the agents' reference; taken from the source so it cannot go stale."""
    out = []
    for mod in ("core", "shell", "openings", "kitchen", "bath", "fixtures", "furniture", "lights"):
        tree = ast.parse(open(os.path.join(PIPE, "kit", mod + ".py")).read())
        out.append("## kit.%s\n\n%s\n" % (mod, ast.get_docstring(tree) or ""))
        if mod == "core":
            out.append("Material keys (the only ones allowed): " + ", ".join(
                k.value for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "VOCAB" for k in n.value.keys) + "\n")
        for n in tree.body:
            defs = [n] if isinstance(n, ast.FunctionDef) else [f for f in n.body if isinstance(f, ast.FunctionDef)] if isinstance(n, ast.ClassDef) else []
            for f in defs:
                if not f.name.startswith("_") or f.name == "__init__":
                    owner = n.name + "." if isinstance(n, ast.ClassDef) else ""
                    out.append("`%s%s(%s)`\n%s\n" % (owner, f.name, ast.unparse(f.args), ast.get_docstring(f) or ""))
    return "\n".join(out)


def prepare_unit(job):
    unit = os.path.join(job, "unit")
    os.makedirs(unit, exist_ok=True)
    open(os.path.join(job, "kit_api.md"), "w").write(api_doc())
    cfg = json.load(open(os.path.join(job, "job.json")))
    json.dump({"title": cfg.get("title", "Your apartment"), "subtitle": cfg.get("subtitle", "")}, open(os.path.join(unit, "meta.json"), "w"))
    # ./unit: the one command agents use to build, check and render; it queues so that parallel agents do not exhaust the GPU
    w = os.path.join(job, "unit.sh")
    open(w, "w").write("""#!/usr/bin/env python3
import fcntl, os, subprocess, sys, time
here = os.path.dirname(os.path.abspath(__file__))
while True:
    for i in range(%d):
        f = open(os.path.join(here, ".slot%%d" %% i), "w")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            continue
        r = subprocess.run([%r, "-b", "--python", %r, "--", os.path.join(here, "unit")] + sys.argv[1:], capture_output=True, text=True)
        keep = [l for l in (r.stdout + r.stderr).split("\\n") if l.startswith("[") or "Error" in l or "error" in l or l.startswith(("Traceback", "  File", "    "))]
        print("\\n".join(keep[-60:]) or "ok")
        sys.exit(r.returncode)
    time.sleep(2)
""" % (SLOTS, BLENDER, os.path.join(HERE, "unit.py")))
    os.chmod(w, 0o755)


def build(job):
    prepare_unit(job)
    sv = json.load(open(os.path.join(job, "survey.json")))
    cfg = json.load(open(os.path.join(job, "job.json")))
    furniture = bool(cfg.get("furniture")) and sv.get("furniture_present", False)
    if not os.path.exists(os.path.join(job, "unit", "shell.py")) or metrics(job).get("shell", {}).get("status") != "end_turn":
        run_agent(job, "shell", "shell", "Working directory: %s\nBuild the shell: write unit/shell.py from survey.json, plan.png and the frames." % job)
    rooms = [r["name"] for r in sv["rooms"]]

    def room(name):
        if metrics(job).get("room_" + name, {}).get("status") == "end_turn":
            return
        r = next(r for r in sv["rooms"] if r["name"] == name)
        msg = ("Working directory: %s\nYour room: %s. Write unit/room_%s.py.\nFurniture: %s\nIts survey entry:\n%s" % (
            job, name, name,
            "model the furniture and loose items the frames show in this room." if furniture else "none; model only what is permanently part of the unit.",
            json.dumps(r, indent=1)))
        return run_agent(job, "room_" + name, "room", msg)

    with ThreadPoolExecutor(len(rooms)) as ex:
        list(ex.map(room, rooms))
    run_agent(job, "check", "check", "Working directory: %s\nAll room files are written. Rooms: %s. Check the whole unit and fix what is wrong." % (job, ", ".join(rooms)))


def bake(job):
    t0 = time.time()
    r = subprocess.run([os.path.join(job, "unit.sh"), "--check", "--bake", os.path.join(job, "site")], capture_output=True, text=True)
    print(r.stdout[-3000:])
    if r.returncode or not os.path.exists(os.path.join(job, "site", "plan.json")):
        raise SystemExit("bake failed")
    # the survey's findings travel with the model so the viewer can say what was guessed and how the scale was found
    p = os.path.join(job, "site", "plan.json")
    d, sv = json.load(open(p)), json.load(open(os.path.join(job, "survey.json")))
    d["survey"] = {"scale": sv.get("scale"), "guessed": [g["room"] for g in sv.get("gaps", []) if g.get("answer") == "guess"]}
    json.dump(d, open(p, "w"))
    metrics(job, "bake", minutes=round((time.time() - t0) / 60, 1), usd=0)


if __name__ == "__main__":
    job, what = os.path.abspath(sys.argv[1]), sys.argv[2]
    for stage in ("ingest", "survey", "build", "bake") if what == "all" else [what]:
        {"ingest": ingest, "survey": survey, "build": build, "bake": bake}[stage](job)
        if stage == "survey" and what == "all" and not os.path.exists(os.path.join(job, "answers.json")) and json.load(open(os.path.join(job, "survey.json"))).get("gaps"):
            print("survey has questions for the user; answer them in answers.json and run again")
            break
    print(json.dumps(metrics(job), indent=1))
