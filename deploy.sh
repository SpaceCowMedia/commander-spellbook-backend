#!/bin/bash

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

# Check if the number of arguments is correct
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 [environment]"
    exit 1
fi

# Get the first CLI argument
APP_ENVIRONMENT=$1

ACCOUNT_ID='083767677168'
REGION='us-east-2'
ECR_REGISTRY=$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com
CLUSTER_NAME=spellbook-prod-cluster
IMAGE_TAG=$(git rev-parse HEAD)

# Configure AWS credentials
ROLE_ARN="arn:aws:iam::$ACCOUNT_ID:role/spellbook-deploy"

# Function to configure the AWS CLI profile with a specific credential source
# These profiles are separate because you cannot have both credential_source
# and source_profile in the same profile, and it is not possible to clear either:
# https://github.com/aws/aws-cli/issues/3346
configure_profile_with_credential_source() {
  local credential_source=$1

  # Configure the profile with the specified credential source
  aws configure set profile.$AWS_PROFILE.role_arn $ROLE_ARN
  aws configure set profile.$AWS_PROFILE.credential_source $credential_source

  echo "Configured profile $AWS_PROFILE with credential source: $credential_source"
}

# Function to configure the AWS CLI profile to use the default profile as source
configure_profile_with_source_profile() {
  local source_profile=$1

  aws configure set profile.$AWS_PROFILE.role_arn $ROLE_ARN
  aws configure set profile.$AWS_PROFILE.source_profile $source_profile

  echo "Configured profile $AWS_PROFILE to use profile ${source_profile} as source"
}

# Function to test the AWS CLI profile by getting the caller identity
aws_test_profile() {
  if aws sts get-caller-identity > /dev/null 2>&1; then
    echo "Successfully assumed role using profile $AWS_PROFILE with $1"
    return 0
  else
    echo "Failed to assume role using profile $AWS_PROFILE with $1"
    return 1
  fi
}

aws_setup_profile() {
  if [ -n "${AWS_PROFILE-}" ]; then
    PARENT_AWS_PROFILE=$AWS_PROFILE
    export AWS_PROFILE="spellbook-deploy-sp"
    configure_profile_with_source_profile $PARENT_AWS_PROFILE
    
    if aws_test_profile "$PARENT_AWS_PROFILE"; then
      return 0
    fi
  else
    echo "AWS_PROFILE is not set. Not trying a parent profile."
  fi

  # Try different credential sources
  export AWS_PROFILE="spellbook-deploy-cs"
  CREDENTIAL_SOURCES=("Ec2InstanceMetadata" "Environment" "EcsContainer")
  for credential_source in "${CREDENTIAL_SOURCES[@]}"; do
    configure_profile_with_credential_source $credential_source
    if aws_test_profile "credential source: $credential_source"; then
      return 0
    fi
  done

  # Attempt to use the default profile as a fallback
  export AWS_PROFILE="spellbook-deploy-sp"
  configure_profile_with_source_profile "default"
  if aws_test_profile "default profile as source"; then
    return 0
  fi

  echo "Failed to assume role with all specified credential sources and the default profile."
  exit 1
}

do_migrations() {
    echo "TODO: implement migrations for production environments..."
    exit 1
}

aws_setup_profile

# Login to Amazon ECR
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

## API
docker build -f backend/Dockerfile --platform linux/amd64 . -t spellbook-backend:latest

# Push image to Amazon ECR
docker tag spellbook-backend:latest $ECR_REGISTRY/spellbook-$APP_ENVIRONMENT-ecr:$IMAGE_TAG
docker tag spellbook-backend:latest $ECR_REGISTRY/spellbook-$APP_ENVIRONMENT-ecr:latest
docker push --all-tags $ECR_REGISTRY/spellbook-$APP_ENVIRONMENT-ecr

if $APP_ENVIRONMENT == "prod"; then
    do_migrations
else
    echo "No migrations to run for non-prod environments."
fi

# Configure kubectl to connect to your cluster
aws eks --region $REGION update-kubeconfig --name $CLUSTER_NAME

# Apply Kubernetes configuration
kubectl apply -k backend/.kubernetes/app/$APP_ENVIRONMENT/

# Rollout pods
kubectl rollout restart deployment/spellbook-api -n spellbook-$APP_ENVIRONMENT
kubectl rollout status deployment/spellbook-api -n spellbook-$APP_ENVIRONMENT --timeout=600s