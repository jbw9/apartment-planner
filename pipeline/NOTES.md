# Upload-to-walkthrough pipeline: where things stand (16 Nov 2026)

A person uploads a floor plan plus photos or video on the website. About 50 minutes later they get a walkable model
of the unit in the same viewer as unit 487. Everything runs on AWS; no local machine is involved.

## Using it

- Upload page: https://d79zv3r1ey4y5.cloudfront.net (creating a job needs the access code)
- Job page: `job.html?id=<job id>` shows progress and any follow-up questions
- Viewer: `index.html?unit=units/<job id>`
- Finished test jobs:
  - 507 E Green on the GPU machine: `index.html?unit=units/a406836b3df2e9ab`
  - 507 E Green on the CPU machine: `index.html?unit=units/94b563395965b9e4`
  - Unit 487: `index.html?unit=units/451039e85677d9eb`

## Not in the repository (needed to deploy from another computer)

- `pipeline/infra/env.sh`: bucket name, Bedrock model ARN, AWS profile and region
- `pipeline/infra/.access_code`: the code the upload page asks for
- AWS credentials for the account, as a profile named `macmini`
- Test inputs and local job folders, on the external drive under `/Volumes/Movies/apt-jobs/`

## How a job runs

1. `start.html` asks whether to include furniture, takes the files, and calls the API (a Lambda, `infra/api.py`).
2. A Step Functions workflow starts a small machine for the survey: frames are pulled from the video and the model
   lists rooms, scale and anything it could not see.
3. If something is missing, the job page asks for a photo of that spot. "Guess" builds it from the floor plan and
   tags it, so the viewer's "Guessed areas" button can tint it. The workflow waits with no machine running.
4. A build machine runs the wall layout, then one agent per room in parallel, then a whole-unit check. The agents
   write short scripts against the parts kit (`pipeline/kit/`), not raw Blender code.
5. The fixed bake (`kit/bake.py`) renders day and lamp lightmaps for four surface groups, and exports the model and
   `plan.json` to the bucket. The viewer loads any unit folder.

## Measured runs (507 E Green and 487, full jobs through the website API)

| Run | Build machine | End to end | Bake | Model cost |
|---|---|---|---|---|
| 507, first cloud run | CPU c7i.12xlarge | 62 min | 18.6 min | $12.54 |
| 487 | CPU c7i.12xlarge | 62 min | 15.8 min | $13.37 |
| 507, GPU run | g4dn.2xlarge (T4) | 48 min | 9.7 min | $11.10 |

End to end includes the wait for follow-up answers, which the tests answered with "guess" within seconds. Machine
cost is extra and small: the GPU machine was up about 37 minutes at $0.75/h. Before the pipeline, one unit took
about 3 hours and $22 to $36.

## What changed on 16 Nov (afternoon)

- GPU quota approved: 8 vCPUs of on-demand G instances, which is one 2xlarge at a time.
- New worker image with NVIDIA drivers (`GPU=1 ./ami.sh`). The image build checks that Blender reports OptiX.
  Previous CPU image: `ami-00451e976ba23a715`, in case of rollback (put it back in SSM `/apartment/worker-ami`).
- Stack now uses `BuildType=g6.2xlarge`.
- The launcher (`api.py`) tries every zone, then `g5.2xlarge`, `g4dn.2xlarge`, and last the CPU `c7i.12xlarge`.
  Reason: the first GPU job failed with "insufficient capacity" for g6.2xlarge, and the second found no g6 or g5
  in any zone and ran on g4dn.
- Survey and wall-layout stages run at medium effort (`worker/stages.py`). Survey went from about 14 to 9 minutes,
  layout from 14 to 9, with an equivalent layout on 507.
- `ami.sh` waits for "running" before "stopped"; without that the wait gave up while the machine was still pending.

## Open items

- No run has yet used the intended g6.2xlarge (L4), so its bake time is unknown. The T4 halved the CPU bake time.
- Splitting the eight bake passes across two GPUs is possible but would save at most a few minutes of a 48-minute
  job; the model stages are now the larger part (survey 9, layout 9, rooms 7, check 8 minutes).
- Only one build can run at a time on the GPU quota; a second concurrent job falls back to the CPU machine.
- Only two apartments have been measured; the plan called for three.
- The viewer header and lighting panel overlap at some window sizes.
- A separate session is adding an "Oasis" lighting mode (`kit/oasis.py`, edits to `kit/lights.py`, `kit/core.py`,
  `kit/bake.py`, `units/e507.py`, viewer files). That work is not described here.

## Deploying

- `pipeline/infra/deploy.sh`: stack, worker code to the bucket, website build and upload
- `pipeline/infra/ami.sh`: worker image (`GPU=1` for the GPU one)
- Pushing to `main` also rebuilds the GitHub Pages copy of the viewer (unit 487 and the planner only)
