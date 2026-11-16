"""One agent loop on Amazon Bedrock: the model works in a directory with a shell and file tools until it says it is
done, or until it hits its turn or dollar limit. State is saved after every turn, so calling run() again with the
same run directory resumes."""
import base64
import json
import os
import subprocess
import time

import boto3
import cv2
from botocore.config import Config

PRICE = {"input_tokens": 4.0, "output_tokens": 20.0, "cache_read_input_tokens": 0.2, "cache_creation_input_tokens": 8.0}  # Opus 5.5, $/MTok, 1 h cache
MAX_OUT = 30000

TOOLS = [
    {"name": "bash", "description": "Run a shell command in the working directory and return its combined stdout and stderr and exit code.",
     "input_schema": {"type": "object", "properties": {
         "command": {"type": "string"},
         "timeout_seconds": {"type": "integer", "description": "Default 120, maximum 900."}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read a file. A text file is returned as text (optionally a line range); an image file (png, jpg) is returned as the image, so this is how you look at an image.",
     "input_schema": {"type": "object", "properties": {
         "path": {"type": "string"}, "offset": {"type": "integer", "description": "First line, 1-based."},
         "limit": {"type": "integer", "description": "Number of lines."}}, "required": ["path"]}},
    {"name": "write_file", "description": "Create or overwrite a text file with the given content.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace one exact occurrence of old_string in a text file with new_string. Fails if old_string is missing or not unique.",
     "input_schema": {"type": "object", "properties": {
         "path": {"type": "string"}, "old_string": {"type": "string"}, "new_string": {"type": "string"}}, "required": ["path", "old_string", "new_string"]}},
]


def _clip(s):
    return s if len(s) <= MAX_OUT else s[:MAX_OUT // 3] + f"\n... [{len(s) - MAX_OUT} characters omitted] ...\n" + s[-2 * MAX_OUT // 3:]


def _tool(work, name, a):
    if name == "bash":
        t = min(int(a.get("timeout_seconds") or 120), 900)
        try:
            r = subprocess.run(a["command"], shell=True, executable="/bin/bash", cwd=work, capture_output=True, text=True, errors="replace", timeout=t)
            return _clip(r.stdout + r.stderr) + f"\n[exit {r.returncode}]"
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or b"") + (e.stderr or b"")
            return _clip(out.decode(errors="replace") if isinstance(out, bytes) else out) + f"\n[killed after {t}s timeout]"
    p = a["path"] if os.path.isabs(a["path"]) else os.path.join(work, a["path"])
    if name == "read_file":
        if p.lower().endswith((".png", ".jpg", ".jpeg")):
            im = cv2.imread(p)
            if im is None:
                return f"cannot read image {p}"
            h, w = im.shape[:2]
            s = 1568 / max(h, w)  # larger images are downscaled by the API anyway
            if s < 1:
                im = cv2.resize(im, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
            data = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tobytes()
            return [{"type": "text", "text": f"{p} ({w}x{h})"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(data).decode()}}]
        lines = open(p, errors="replace").read().split("\n")
        o = max(int(a.get("offset") or 1), 1)
        return _clip("\n".join(lines[o - 1:o - 1 + int(a["limit"])] if a.get("limit") else lines[o - 1:]))
    if name == "write_file":
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        open(p, "w").write(a["content"])
        return f"wrote {p}"
    if name == "edit_file":
        s = open(p).read()
        n = s.count(a["old_string"])
        if n != 1:
            return f"old_string occurs {n} times in {p}; it must occur exactly once"
        open(p, "w").write(s.replace(a["old_string"], a["new_string"]))
        return f"edited {p}"
    return f"unknown tool {name}"


def run(run_dir, work, model, system, job, effort="high", max_usd=10.0, max_turns=250):
    """run_dir holds this agent's log and state; work is the directory its commands run in (shared between agents).
    Returns the summary that is also written to run_dir/summary.json."""
    os.makedirs(run_dir, exist_ok=True)
    state = os.path.join(run_dir, "messages.json")
    if os.path.exists(state):
        st = json.load(open(state))
    else:
        st = {"messages": [{"role": "user", "content": job}], "usage": {k: 0 for k in PRICE}, "turns": 0, "seconds": 0.0, "tools": {}, "images": 0}
    msgs, usage = st["messages"], st["usage"]
    client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"),
                          config=Config(read_timeout=3600, retries={"max_attempts": 8, "mode": "adaptive"}))

    def log(d):
        with open(os.path.join(run_dir, "run.jsonl"), "a") as f:
            f.write(json.dumps(d) + "\n")

    cost = lambda: sum(usage[k] * PRICE[k] for k in PRICE) / 1e6
    t0 = time.time() - st["seconds"]
    status = "max_turns"
    while st["turns"] < max_turns:
        body = {"anthropic_version": "bedrock-2023-05-31", "max_tokens": 64000, "system": system, "messages": msgs, "tools": TOOLS,
                "thinking": {"type": "adaptive"}, "output_config": {"effort": effort}, "cache_control": {"type": "ephemeral", "ttl": "1h"}}
        for attempt in range(12):   # Bedrock has minutes-long unavailable spells; ride them out rather than lose the job
            try:
                resp = json.loads(client.invoke_model(modelId=model, body=json.dumps(body))["body"].read())
                break
            except Exception as e:
                log({"type": "api_error", "attempt": attempt, "error": str(e)[:500]})
                if attempt == 11:
                    raise
                time.sleep(min(30 * (attempt + 1), 120))
        st["turns"] += 1
        for k in PRICE:
            usage[k] += resp["usage"].get(k) or 0
        msgs.append({"role": "assistant", "content": resp["content"]})
        calls = [b for b in resp["content"] if b["type"] == "tool_use"]
        log({"type": "assistant", "turn": st["turns"], "stop": resp["stop_reason"], "usage": resp["usage"], "cost_usd": round(cost(), 3),
             "text": [b["text"] for b in resp["content"] if b["type"] == "text"], "calls": [{"name": b["name"], "input": b["input"]} for b in calls]})
        if resp["stop_reason"] == "tool_use":
            results = []
            for b in calls:
                try:
                    out = _tool(work, b["name"], b["input"])
                except Exception as e:
                    out = f"error: {type(e).__name__}: {e}"
                st["tools"][b["name"]] = st["tools"].get(b["name"], 0) + 1
                st["images"] += isinstance(out, list)
                log({"type": "tool_result", "name": b["name"], "result": out if isinstance(out, str) else out[0]["text"] + " [image]"})
                results.append({"type": "tool_result", "tool_use_id": b["id"], "content": out})
            if cost() > max_usd * 0.85 and not st.get("warned"):
                # one warning so the agent can leave its files in a working state instead of being cut off mid-edit
                st["warned"] = True
                results.append({"type": "text", "text": "Budget notice: this job is almost out of budget. Finish the edit in hand, make sure your files run, write your result file and stop."})
            msgs.append({"role": "user", "content": results})
        elif resp["stop_reason"] == "max_tokens":
            msgs.append({"role": "user", "content": "Your last message was cut off at the output limit. Continue from where you stopped."})
        else:
            status = resp["stop_reason"]
            break
        st["seconds"] = time.time() - t0
        json.dump(st, open(state + ".tmp", "w"))
        os.replace(state + ".tmp", state)
        if cost() > max_usd:
            status = "cost_limit"
            break
    final = [b["text"] for b in msgs[-1]["content"] if isinstance(b, dict) and b.get("type") == "text"] if msgs[-1]["role"] == "assistant" else []
    summary = {"status": status, "model": model, "effort": effort, "turns": st["turns"], "minutes": round((time.time() - t0) / 60, 1),
               "cost_usd": round(cost(), 2), "usage": usage, "tools": st["tools"], "images_opened": st["images"], "final_reply": "\n".join(final)}
    json.dump(summary, open(os.path.join(run_dir, "summary.json"), "w"), indent=1)
    return summary
