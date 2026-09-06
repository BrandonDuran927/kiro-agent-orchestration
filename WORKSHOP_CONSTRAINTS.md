# Workshop Engineering Constraints

These are organizational and workshop constraints, not a solution architecture diagram.

The Solution Architect must design the **smallest** solution that satisfies the approved requirements while staying inside these boundaries.

## Platform

- AWS only.
- Infrastructure must be provisioned and updated using Terraform.
- The backend runtime must be Python.
- The frontend must be static HTML, CSS, and JavaScript. Do not introduce a frontend framework unless an approved requirement truly needs one.

## Approved AWS service catalog

The POC may use only the following AWS services:

- Amazon S3
- Amazon CloudFront
- Amazon API Gateway
- AWS Lambda
- Amazon DynamoDB
- Amazon CloudWatch
- AWS IAM

Do not add other AWS services unless the facilitator explicitly changes the constraints.

## Hosting and networking constraints

- The POC does **not** need a custom domain.
- Do not use Route 53, ACM, or custom DNS/domain configuration.
- The generated CloudFront distribution URL is sufficient for the workshop frontend.
- Frontend object storage must not be directly public.
- Do not use EC2, ECS, EKS, load balancers, VPCs, NAT Gateways, or continuously running application servers.

## Backend and persistence constraints

- Backend capabilities must be exposed using approved managed/serverless AWS services.
- Persistent application data must use an approved serverless data store.
- Prefer consumption-based/on-demand capacity for the POC.

## Security constraints

- Keep frontend storage private.
- Follow least privilege for IAM.
- Do not embed AWS credentials, secrets, or account credentials in source code or frontend assets.
- Document accepted POC risks rather than introducing extra services for production concerns that are explicitly out of scope.

## Cost and scope constraints

- Optimize for negligible idle cost and short workshop cleanup.
- Choose the fewest components needed to satisfy the requirements.
- Do not add services or features for hypothetical future scale.
- Avoid production-grade extras unless required by an approved requirement.

## Design principle

The approved service list tells you **what you are allowed to use**, not how the services must be connected.

The architecture must be derived from the approved requirements plus these constraints.
