VPS Deployment Guide
Prerequisites on VPS
# 1. Update system
sudo apt update && sudo apt upgrade -y
# 2. Install Docker
sudo apt install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
# 3. Install curl (usually pre-installed)
sudo apt install -y curl
# 4. Disable UFW (or configure firewall rules)
sudo ufw disable
# OR allow required ports:
# sudo ufw allow 22/tcp 80/tcp 443/tcp 6443/tcp
# 5. Log out and back in (for docker group)
exit
Clone and Deploy
# SSH back in
ssh your-user@your-vps-ip
# Clone repository
git clone https://github.com/your-org/some-kind-of-irc.git
cd some-kind-of-irc
# Set ANTHROPIC_API_KEY (required for AI features)
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
# Make script executable and run
chmod +x run_locally_k3s.sh
./run_locally_k3s.sh
What the Script Does (8 steps)
Step	Action
1/8	Check prerequisites (docker, curl)
2/8	Verify ports 80/443 are free
3/8	Install K3s (idempotent)
4/8	Install Argo CD
5/8	Install NGINX Ingress
6/8	Deploy Redis + PostgreSQL
7/8	Build & deploy all services (monolith, ai-service, ai-service-adk, data-processor, minio, media-storage, audit-logger, frontend) + run migrations
8/8	Configure ingress routes
Then: Inject ANTHROPIC_API_KEY, create MinIO bucket, seed users.
Verify Deployment
# Check pods
kubectl get pods -n irc-app
# Test endpoints
curl http://localhost/health
curl http://localhost/healthz
curl http://localhost/adk/healthz
curl http://localhost/data-processor/healthz
# Access from external IP
curl http://<VPS_IP>/health
---
Ready to deploy? The script is well-documented and handles everything automatically. Just ensure Docker is installed and ports 80/443 are free on your VPS.
