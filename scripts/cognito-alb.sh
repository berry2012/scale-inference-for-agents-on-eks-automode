COK_AWS_REGION=us-east-2 
COK_ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
COK_MY_DOMAIN=example.com 
COK_ECR_REPO=SummitAssistant

# Request an ACM certificate:

COK_ACM_CERT_ARN=$(aws acm request-certificate \
  --domain-name "SummitAssistant.${COK_MY_DOMAIN}" \
  --validation-method DNS \
  --idempotency-token 1234 \
  --options CertificateTransparencyLoggingPreference=DISABLED \
  --region $COK_AWS_REGION \
  --query 'CertificateArn' \
  --output text)

aws acm describe-certificate \
  --certificate-arn $COK_ACM_CERT_ARN \
  --region $COK_AWS_REGION \
  --query 'Certificate.Status'

# Create an Amazon Cognito user pool:
COK_COGNITO_USER_POOL_ID=$(aws cognito-idp create-user-pool \
  --pool-name MyUserPool \
  --username-attributes email \
  --username-configuration=CaseSensitive=false \
  --region $COK_AWS_REGION \
  --query 'UserPool.Id' \
  --auto-verified-attributes email \
  --account-recovery-setting 'RecoveryMechanisms=[{Priority=1,Name=verified_email},{Priority=2,Name=verified_phone_number}]' \
  --output text)

# Create a user pool app client:
COK_COGNITO_USER_POOL_CLIENT_ID=$(aws cognito-idp create-user-pool-client \
  --client-name MyAppClient \
  --user-pool-id $COK_COGNITO_USER_POOL_ID \
  --generate-secret \
  --region $COK_AWS_REGION \
  --query 'UserPoolClient.ClientId' \
  --output text)

# Configure the app client:
aws cognito-idp update-user-pool-client \
  --client-id $COK_COGNITO_USER_POOL_CLIENT_ID \
  --user-pool-id $COK_COGNITO_USER_POOL_ID \
  --region $COK_AWS_REGION \
  --allowed-o-auth-flows code \
  --callback-urls "https://SummitAssistant.${COK_MY_DOMAIN}/oauth2/idpresponse" \
  --allowed-o-auth-flows-user-pool-client \
  --allowed-o-auth-scopes openid \
  --supported-identity-providers COGNITO    

COK_COGNITO_DOMAIN=SummitAssistant

aws cognito-idp create-user-pool-domain \
  --user-pool-id $COK_COGNITO_USER_POOL_ID \
  --region $COK_AWS_REGION \
  --domain $COK_COGNITO_DOMAIN  

# ALB Annotations
"""
    alb.ingress.kubernetes.io/auth-type: cognito
    alb.ingress.kubernetes.io/auth-scope: openid
    alb.ingress.kubernetes.io/auth-session-timeout: '3600'
    alb.ingress.kubernetes.io/auth-session-cookie: AWSELBAuthSessionCookie
    alb.ingress.kubernetes.io/auth-on-unauthenticated-request: authenticate
    alb.ingress.kubernetes.io/auth-idp-cognito: '{"UserPoolArn": "$(aws cognito-idp describe-user-pool --user-pool-id $COK_COGNITO_USER_POOL_ID --region $COK_AWS_REGION --query 'UserPool.Arn' --output text)","UserPoolClientId":"${COK_COGNITO_USER_POOL_CLIENT_ID}","UserPoolDomain":"${COK_COGNITO_DOMAIN}.auth.${COK_AWS_REGION}.amazoncognito.com"}'
    alb.ingress.kubernetes.io/certificate-arn: $COK_ACM_CERT_ARN   
"""

echo COK_COGNITO_USER_POOL_CLIENT_ID: ${COK_COGNITO_USER_POOL_CLIENT_ID} 
echo COK_COGNITO_DOMAIN: ${COK_COGNITO_DOMAIN}
echo COK_AWS_REGION: ${COK_AWS_REGION}

