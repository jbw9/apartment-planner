#!/usr/bin/env python3
"""Runs a job's stages on a server: fetches the job from S3, runs them, keeps the job's row and its preview stills up to
date while it works, publishes the finished model, and tells the workflow how it went.

usage: cloud.py <bucket> <table> <job-id> <task-token> <stage>..."""
import glob
import json
import os
import subprocess
import sys
import threading
import traceback
from decimal import Decimal

import boto3
import cv2

import stages

B, TABLE, JOB, TOKEN = sys.argv[1:5]
DIR = "/opt/apartment/jobs/" + JOB
db = boto3.resource("dynamodb").Table(TABLE)
dec = lambda o: json.loads(json.dumps(o), parse_float=Decimal)
sync = lambda *a: subprocess.run(["aws", "s3", "sync", "--only-show-errors", *a], check=True)


def row(**kw):
    names = {"#" + k: k for k in kw}
    db.update_item(Key={"job_id": JOB}, UpdateExpression="SET " + ", ".join("#%s = :%s" % (k, k) for k in kw),
                   ExpressionAttributeNames=names, ExpressionAttributeValues={":" + k: dec(v) for k, v in kw.items()})


def progress(stop):
    """Every half minute: save the working files, and publish new preview renders so the person has something to watch."""
    sent = {}
    while not stop.wait(30):
        try:
            for p in sorted(glob.glob(DIR + "/unit/renders/*.png")):
                if sent.get(p) != os.path.getmtime(p):
                    sent[p] = os.path.getmtime(p)
                    name = os.path.basename(p)[:-4] + ".jpg"
                    cv2.imwrite("/tmp/" + name, cv2.imread(p), [cv2.IMWRITE_JPEG_QUALITY, 85])
                    boto3.client("s3").upload_file("/tmp/" + name, B, "public/units/%s/stills/%s" % (JOB, name), ExtraArgs={"ContentType": "image/jpeg", "CacheControl": "no-cache"})
            row(stills=sorted(os.path.basename(p)[:-4] for p in sent), metrics=stages.metrics(DIR))
            sync(DIR, "s3://%s/jobs/%s" % (B, JOB), "--exclude", "inputs/*", "--exclude", "frames/*", "--exclude", "site/*", "--exclude", "*.blend1")
        except Exception:
            traceback.print_exc()


os.makedirs(DIR, exist_ok=True)
sync("s3://%s/jobs/%s" % (B, JOB), DIR)
sfn, stop = boto3.client("stepfunctions"), threading.Event()
threading.Thread(target=progress, args=(stop,), daemon=True).start()
try:
    for stage in sys.argv[5:]:
        if stage == "build":
            row(status="building")
            sv = json.load(open(DIR + "/survey.json"))
            if sv.get("gaps") and not os.path.exists(DIR + "/answers.json"):   # nobody answered in time: guess them all
                json.dump({g["id"]: "guess" for g in sv["gaps"]}, open(DIR + "/answers.json", "w"))
        getattr(stages, stage)(DIR)
    stop.set()
    sync(DIR, "s3://%s/jobs/%s" % (B, JOB), "--exclude", "inputs/*", "--exclude", "frames/*", "--exclude", "*.blend1")
    gaps = json.load(open(DIR + "/survey.json")).get("gaps", [])
    if os.path.exists(DIR + "/site/plan.json"):
        sync(DIR + "/site", "s3://%s/public/units/%s" % (B, JOB))
        row(status="done", metrics=stages.metrics(DIR))
    else:
        row(gaps=gaps, metrics=stages.metrics(DIR))
    sfn.send_task_success(taskToken=TOKEN, output=json.dumps({"gaps": len(gaps)}))
except BaseException as e:
    traceback.print_exc()
    stop.set()
    sfn.send_task_failure(taskToken=TOKEN, error=type(e).__name__, cause=str(e)[:250])
