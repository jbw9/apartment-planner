#!/bin/bash
# Deploys everything: stack, pipeline code for the workers, and the website.
#   ./deploy.sh      (run from anywhere; reads env.sh and .access_code beside it)
set -euo pipefail
cd "$(dirname "$0")"
. ./env.sh   # APT_BUCKET, APT_MODEL, AWS_PROFILE, AWS_REGION
B=$APT_BUCKET

zip -qj /tmp/apartment-api.zip api.py
KEY=lambda/api-$(shasum /tmp/apartment-api.zip | cut -c1-12).zip   # a new key each change, or the function is not updated
aws s3 cp /tmp/apartment-api.zip "s3://$B/$KEY" --only-show-errors
aws cloudformation deploy --stack-name apartment --template-file stack.yaml --capabilities CAPABILITY_NAMED_IAM \
  --tags project=apartment --no-fail-on-empty-changeset \
  --parameter-overrides Bucket=$B ApiCodeKey="$KEY" AccessCode="${ACCESS_CODE:-$(cat .access_code)}" ModelArn=$APT_MODEL ${BUILD_TYPE:+BuildType=$BUILD_TYPE}
# browsers upload straight to the bucket with signed links
aws s3api put-bucket-cors --bucket $B --cors-configuration \
  '{"CORSRules":[{"AllowedMethods":["PUT"],"AllowedOrigins":["*"],"AllowedHeaders":["*"],"MaxAgeSeconds":3000}]}'

aws s3 sync .. "s3://$B/pipeline" --only-show-errors --delete --exclude "*__pycache__*" --exclude "infra/*" --exclude "units/*" --exclude ".*"
aws s3 sync ../../public/tex "s3://$B/pipeline/tex" --only-show-errors

(cd ../.. && npx vite build --base ./ >/dev/null)
aws s3 sync ../../dist "s3://$B/public" --only-show-errors
DIST=$(aws cloudformation describe-stacks --stack-name apartment --query "Stacks[0].Outputs[?OutputKey=='Distribution'].OutputValue" --output text)
aws cloudfront create-invalidation --distribution-id "$DIST" --paths "/*.html" "/" >/dev/null
aws cloudformation describe-stacks --stack-name apartment --query "Stacks[0].Outputs[?OutputKey=='Url'].OutputValue" --output text
