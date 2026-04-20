#!/bin/bash
# Setup S3 bucket 

set -e

BUCKET_NAME="${S3_BUCKET_NAME:-summitassistant-demo-bucket}"
REGION="${S3_REGION:-us-east-1}"

echo "Setting up S3 bucket: $BUCKET_NAME"
echo "Region: $REGION"


# Create bucket
echo "Creating S3 bucket..."
aws s3 mb "s3://$BUCKET_NAME" --region "$REGION" 2>/dev/null || echo "Bucket already exists or creation skipped"

# Verify bucket exists
echo "Verifying bucket..."
if aws s3 ls "s3://$BUCKET_NAME" > /dev/null 2>&1; then
    echo "✓ Bucket $BUCKET_NAME is ready"
else
    echo "✗ Failed to verify bucket"
    exit 1
fi

echo "S3 setup complete!"
