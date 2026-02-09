## 1. Storage Service
- [x] 1.1 Create Flask storage service skeleton and app entrypoint
- [x] 1.2 Implement MinIO client configuration and bucket targeting
- [x] 1.3 Add /upload endpoint with backend auth verification
- [x] 1.4 Enforce file size and MIME validation (jpeg/png/webp, 10 MB)
- [x] 1.5 Add /media/<key> redirect endpoint for public access

## 2. Backend Integration
- [x] 2.1 Add optional image_url field to message schema and model
- [x] 2.2 Accept image_url on message creation and include in responses
- [x] 2.3 Include image_url in real-time message broadcasts

## 3. Documentation
- [x] 3.1 Document storage service configuration and environment variables
- [x] 3.2 Provide a minimal upload example for developers

## 4. Docker
- [x] 4.1 Add media storage Dockerfile
- [x] 4.2 Add media storage service to docker-compose with env wiring
