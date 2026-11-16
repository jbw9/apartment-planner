#!/bin/bash
# Builds the worker image (Blender, ffmpeg, Python with boto3 and OpenCV) and records it where the launcher looks.
# Run after deploy.sh, which creates the instance profile this uses. For the GPU image pass a base image that already
# has NVIDIA drivers:  BASE=<ami-id> ./ami.sh
set -euo pipefail
cd "$(dirname "$0")"
. ./env.sh
B=$APT_BUCKET
BLENDER=blender-5.3.0-linux-x64
BASE=${BASE:-$(aws ssm get-parameter --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id --query Parameter.Value --output text)}

cat > /tmp/apartment-ami.sh <<EOF
#!/bin/bash
exec > /var/log/apartment-ami.log 2>&1
set -x
shutdown -h +60
export DEBIAN_FRONTEND=noninteractive HOME=/root
apt-get update
apt-get install -y python3-venv ffmpeg poppler-utils xz-utils unzip curl libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6 libegl1 libice6
curl -sL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscli.zip && unzip -q /tmp/awscli.zip -d /tmp && /tmp/aws/install
python3 -m venv /opt/apartment/venv
/opt/apartment/venv/bin/pip install boto3 numpy opencv-python-headless
# our own copy of the installer: the public mirrors are slow and sometimes down
aws s3 cp s3://$B/installers/$BLENDER.tar.xz /tmp/blender.tar.xz --only-show-errors || {
  curl -sL https://mirrors.ocf.berkeley.edu/blender/release/Blender5.3/$BLENDER.tar.xz -o /tmp/blender.tar.xz
  aws s3 cp /tmp/blender.tar.xz s3://$B/installers/$BLENDER.tar.xz --only-show-errors; }
tar -xJf /tmp/blender.tar.xz -C /opt && ln -sf /opt/$BLENDER/blender /usr/local/bin/blender
rm -rf /tmp/blender.tar.xz /tmp/aws /tmp/awscli.zip
cat >> /etc/environment <<ENV
BLENDER=/usr/local/bin/blender
KIT_TEX=/opt/apartment/pipeline/tex
BLENDER_SLOTS=4
ENV
blender -b --python-expr "import bpy; print('blender ok', bpy.app.version_string)" && touch /opt/apartment/ready
aws s3 cp /var/log/apartment-ami.log s3://$B/installers/ami.log --only-show-errors
shutdown -h now
EOF

ID=$(aws ec2 run-instances --image-id "$BASE" --instance-type c7i.large --iam-instance-profile Name=apartment-worker \
  --user-data file:///tmp/apartment-ami.sh --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=30,VolumeType=gp3}' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=project,Value=apartment},{Key=Name,Value=apartment-ami-build}]' \
  --query 'Instances[0].InstanceId' --output text)
echo "building on $ID"
aws ec2 wait instance-exists --instance-ids "$ID"   # a new instance is not visible to every call at once
aws ec2 wait instance-stopped --instance-ids "$ID"   # the script shuts the instance down when it is finished
aws s3 cp "s3://$B/installers/ami.log" - | grep -q "blender ok" || { echo "install failed; see s3://$B/installers/ami.log"; aws ec2 terminate-instances --instance-ids "$ID" >/dev/null; exit 1; }
AMI=$(aws ec2 create-image --instance-id "$ID" --name "apartment-worker-$(date +%Y%m%d-%H%M)" \
  --tag-specifications 'ResourceType=image,Tags=[{Key=project,Value=apartment}]' 'ResourceType=snapshot,Tags=[{Key=project,Value=apartment}]' --query ImageId --output text)
aws ec2 wait image-available --image-ids "$AMI"
aws ec2 terminate-instances --instance-ids "$ID" >/dev/null
aws ssm put-parameter --name /apartment/worker-ami --type String --overwrite --value "$AMI" >/dev/null
echo "worker image: $AMI"
