# Option C - AWS enterprise reference design (design only, NOT deployed or tested)

Users -> CloudFront (CDN) -> S3 (frontend)
      -> API Gateway (REST) -> Lambda (Python) -> DynamoDB (conditional writes for capacity)
      -> API Gateway WebSocket API -> Lambda (connect/disconnect/broadcast) -> connection table
Cognito (auth, groups: attendee/organizer/admin) | SNS/SES (notifications) | CloudWatch (logs, alarms) | Secrets Manager
Capacity check: DynamoDB UpdateItem with ConditionExpression "going_count < max_capacity" (same idea as the SQL atomic UPDATE).
Azure: Static Web Apps + Functions + Cosmos DB + SignalR + Entra ID. GCP: Firebase Hosting + Cloud Run/Functions + Firestore + Firebase Auth.
