"""The one Lambda behind the website and the workflow.

Called by the website through CloudFront (/api/...):
  POST /api/jobs                 {code, title, furniture, files: [{name, kind: "plan"|"media"}]} -> {job_id, uploads}
  POST /api/jobs/<id>/start      begin the survey
  GET  /api/jobs/<id>            status, gaps, stills, metrics
  POST /api/jobs/<id>/files      {files: [{name, gap}]} -> {uploads}     follow-up photos for a gap
  POST /api/jobs/<id>/answers    {answers: {gap id: "provided"|"guess"}}  resume the workflow
Called by Step Functions: {action: "launch"|"ask"|"fail", job_id, token, ...}."""
import base64
import datetime
import json
import os
import re
import secrets

import boto3

B, TABLE = os.environ["BUCKET"], os.environ["TABLE"]
s3 = boto3.client("s3")
db = boto3.resource("dynamodb").Table(TABLE)

USER_DATA = """#!/bin/bash
exec > /var/log/apartment.log 2>&1
shutdown -h +{minutes}   # hard stop, so a stuck job cannot bill forever
export HOME=/root AWS_REGION={region} AWS_DEFAULT_REGION={region} APT_MODEL={model}
set -a; . /etc/environment; set +a   # where the image records Blender's path
aws s3 sync s3://{bucket}/pipeline /opt/apartment/pipeline --only-show-errors --delete
/opt/apartment/venv/bin/python /opt/apartment/pipeline/worker/cloud.py {bucket} {table} {job} '{token}' {stages}
aws s3 cp /var/log/apartment.log s3://{bucket}/jobs/{job}/logs/{name}.log --only-show-errors
shutdown -h now
"""


def reply(code, body):
    return {"statusCode": code, "headers": {"content-type": "application/json"}, "body": json.dumps(body, default=float)}


def put_url(job, name):
    return s3.generate_presigned_url("put_object", Params={"Bucket": B, "Key": "jobs/%s/inputs/%s" % (job, name)}, ExpiresIn=3600)


def clean(name):
    stem, _, ext = name.rpartition(".")
    return re.sub(r"[^A-Za-z0-9]+", "_", stem or ext).strip("_")[:40] + ("." + re.sub(r"[^A-Za-z0-9]", "", ext).lower() if stem else "")


def workflow(ev):
    job, act = ev["job_id"], ev["action"]
    if act == "launch":
        ami = boto3.client("ssm").get_parameter(Name="/apartment/worker-ami")["Parameter"]["Value"]
        ud = USER_DATA.format(model=os.environ["MODEL"], minutes=ev["minutes"], region=os.environ["AWS_REGION"], bucket=B, table=TABLE, job=job, token=ev["token"],
                              stages=ev["stages"], name=ev["name"])
        boto3.client("ec2").run_instances(
            ImageId=ami, InstanceType=ev["type"], MinCount=1, MaxCount=1, UserData=ud, InstanceInitiatedShutdownBehavior="terminate",
            IamInstanceProfile={"Name": os.environ["PROFILE"]}, SecurityGroupIds=[os.environ["SG"]],
            BlockDeviceMappings=[{"DeviceName": "/dev/sda1", "Ebs": {"VolumeSize": 60, "VolumeType": "gp3"}}],
            TagSpecifications=[{"ResourceType": t, "Tags": [{"Key": "project", "Value": "apartment"}, {"Key": "Name", "Value": "apartment-%s-%s" % (ev["name"], job)}]}
                               for t in ("instance", "volume")])
    elif act == "ask":   # the workflow now waits, with no server running, until the website posts the answers
        db.update_item(Key={"job_id": job}, UpdateExpression="SET #s = :s, ask_token = :t", ExpressionAttributeNames={"#s": "status"},
                       ExpressionAttributeValues={":s": "asking", ":t": ev["token"]})
    elif act == "fail":
        db.update_item(Key={"job_id": job}, UpdateExpression="SET #s = :s, #e = :e", ExpressionAttributeNames={"#s": "status", "#e": "error"},
                       ExpressionAttributeValues={":s": "failed", ":e": json.dumps(ev.get("error"))[:1000]})


def handler(ev, _ctx):
    if "action" in ev:
        return workflow(ev)
    method, path = ev["requestContext"]["http"]["method"], ev["rawPath"].rstrip("/")
    raw = ev.get("body") or "{}"
    body = json.loads(base64.b64decode(raw) if ev.get("isBase64Encoded") else raw)
    m = re.fullmatch(r"/api/jobs(?:/([a-z0-9]{16})(?:/(start|files|answers))?)?", path)
    if not m:
        return reply(404, {"error": "not found"})
    job, sub = m.groups()
    if not job:
        if method != "POST" or not secrets.compare_digest(str(body.get("code", "")), os.environ["ACCESS_CODE"]):
            return reply(403, {"error": "That access code is not right."})
        day = "day#" + datetime.date.today().isoformat()
        try:   # one counter row per day keeps a leaked code from running up a bill
            db.update_item(Key={"job_id": day}, UpdateExpression="ADD n :one", ConditionExpression="attribute_not_exists(n) OR n < :cap",
                           ExpressionAttributeValues={":one": 1, ":cap": int(os.environ["DAILY_CAP"])})
        except db.meta.client.exceptions.ConditionalCheckFailedException:
            return reply(429, {"error": "Today's limit has been reached. Try again tomorrow."})
        job = secrets.token_hex(8)
        files, uploads, n = body.get("files", [])[:200], [], 0
        for f in files:
            if f.get("kind") == "plan":
                n += 1
                name = ("plan" if n == 1 else "plan_%d" % n) + "." + clean(f["name"]).rpartition(".")[2]
            else:
                name = "m_" + clean(f["name"])   # the prefix keeps an upload called plan.jpg from being taken for the plan
            uploads.append({"name": f["name"], "url": put_url(job, name)})
        s3.put_object(Bucket=B, Key="jobs/%s/job.json" % job, Body=json.dumps({"title": str(body.get("title") or "Your apartment")[:80], "furniture": bool(body.get("furniture"))}))
        db.put_item(Item={"job_id": job, "status": "uploading", "title": str(body.get("title") or "Your apartment")[:80],
                          "furniture": bool(body.get("furniture")), "created": datetime.datetime.utcnow().isoformat() + "Z"})
        return reply(200, {"job_id": job, "uploads": uploads})
    item = db.get_item(Key={"job_id": job}).get("Item")
    if not item:
        return reply(404, {"error": "No such job."})
    if sub == "start" and method == "POST":
        if item["status"] != "uploading":
            return reply(409, {"error": "Already started."})
        db.update_item(Key={"job_id": job}, UpdateExpression="SET #s = :s", ExpressionAttributeNames={"#s": "status"}, ExpressionAttributeValues={":s": "surveying"})
        boto3.client("stepfunctions").start_execution(stateMachineArn=os.environ["MACHINE"], name=job, input=json.dumps({"job_id": job}))
        return reply(200, {"ok": True})
    if sub == "files" and method == "POST":
        return reply(200, {"uploads": [{"name": f["name"], "url": put_url(job, "%s_%s" % (re.sub(r"\W", "", str(f["gap"]))[:8], clean(f["name"])))}
                                       for f in body.get("files", [])[:60]]})
    if sub == "answers" and method == "POST":
        if item["status"] != "asking":
            return reply(409, {"error": "Not waiting for answers."})
        s3.put_object(Bucket=B, Key="jobs/%s/answers.json" % job, Body=json.dumps(body.get("answers", {})))
        db.update_item(Key={"job_id": job}, UpdateExpression="SET #s = :s REMOVE ask_token", ExpressionAttributeNames={"#s": "status"}, ExpressionAttributeValues={":s": "building"})
        boto3.client("stepfunctions").send_task_success(taskToken=item["ask_token"], output="{}")
        return reply(200, {"ok": True})
    if not sub and method == "GET":
        item.pop("ask_token", None)
        if item.get("gaps"):
            item["plan_url"] = s3.generate_presigned_url("get_object", Params={"Bucket": B, "Key": "jobs/%s/plan.png" % job}, ExpiresIn=3600)
        return reply(200, item)
    return reply(405, {"error": "not allowed"})
