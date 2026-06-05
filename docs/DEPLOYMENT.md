# Deployment Guide — Hetzner Cloud

**Stack:** Django 5 + Gunicorn | PostgreSQL 16 | Redis 7 | Nginx | Docker Compose  
**CI/CD:** GitHub Actions → GHCR → Hetzner CX22  
**Domain:** booket.uz  
**Storage:** Hetzner local disk (40 GB) — static files, media uploads, PostgreSQL data

---

## Overview

```
GitHub push → Actions build image → push to GHCR → SSH to Hetzner → pull & restart web
```

All services (app, database, Redis, nginx) run as Docker containers on a single Hetzner CX22.  
Static files are collected into the `staticfiles` volume and served by nginx.  
Media uploads land in the `mediafiles` volume, also served by nginx.  
No external storage services needed.

---

## Part 1 — Hetzner Server Setup

### 1.1 Create the server

In [Hetzner Cloud Console](https://console.hetzner.cloud/):

1. **+ Create Server**
2. Location: **Helsinki (hel1)** — lowest latency from Uzbekistan (~50 ms)
3. Image: **Ubuntu 24.04**
4. Type: **CX22** (2 vCPU, 4 GB RAM, 40 GB disk, ~€4.35/month)
5. SSH keys: upload your public key (`~/.ssh/id_ed25519.pub`)
6. Backups: **enable** (adds ~€0.87/month, keeps 7 daily backups automatically)
7. Name: `blackstick-prod`
8. **Create & Buy**

Note the server's **IPv4 address** — referred to as `<SERVER_IP>` below.

### 1.2 Configure the firewall

Hetzner Console → **Firewalls** → **Create Firewall**:

| Direction | Protocol | Port | Source |
|-----------|----------|------|--------|
| Inbound | TCP | 22 | Your IP only |
| Inbound | TCP | 80 | Any |
| Inbound | TCP | 443 | Any |

Apply the firewall to `blackstick-prod`.

### 1.3 Initial server setup

```bash
ssh root@<SERVER_IP>
```

```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker

# Create a non-root deploy user
adduser deploy
usermod -aG sudo,docker deploy

# Copy SSH keys to deploy user
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy

# Create app directory
mkdir -p /opt/blackstick
chown deploy:deploy /opt/blackstick

# Create local backup directory
mkdir -p /opt/backups
chown deploy:deploy /opt/backups
```

Log out from root. All future work is done as `deploy`:

```bash
ssh deploy@<SERVER_IP>
```

### 1.4 Create environment files on the server

```bash
cd /opt/blackstick
```

**`.env`** — Django app environment:

```bash
cat > /opt/blackstick/.env << 'EOF'
DEBUG=0
SECRET_KEY=REPLACE_ME
FERNET_KEY=REPLACE_ME

ALLOWED_HOSTS=booket.uz,www.booket.uz
CSRF_TRUSTED_ORIGINS=https://booket.uz,https://www.booket.uz
CORS_ALLOWED_ORIGINS=https://booket.uz

# Database (must match .env.db)
DB_NAME=blackstick
DB_USER=blackstick
DB_PASSWORD=REPLACE_ME
DB_HOST=db
DB_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/1

# Transactional email (AWS SES)
AWS_SES_USER_ACCESS_KEY_ID=REPLACE_ME
AWS_SES_USER_SECRET_ACCESS_KEY=REPLACE_ME

# SMS via Eskiz
ESKIZ_EMAIL=REPLACE_ME
ESKIZ_PASSWORD=REPLACE_ME
EOF

chmod 600 /opt/blackstick/.env
```

**`.env.db`** — Postgres container:

```bash
cat > /opt/blackstick/.env.db << 'EOF'
POSTGRES_DB=blackstick
POSTGRES_USER=blackstick
POSTGRES_PASSWORD=REPLACE_ME
EOF

chmod 600 /opt/blackstick/.env.db
```

> `DB_PASSWORD` in `.env` and `POSTGRES_PASSWORD` in `.env.db` must be identical.

**Generate secrets:**

```bash
# SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# FERNET_KEY (requires cryptography package)
pip3 install cryptography --quiet
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Part 2 — DNS Configuration

In your domain registrar's DNS panel, add:

```
A   booket.uz       <SERVER_IP>   TTL 300
A   www.booket.uz   <SERVER_IP>   TTL 300
```

Verify propagation before issuing SSL:

```bash
nslookup booket.uz
# Should return <SERVER_IP>
```

---

## Part 3 — GitHub Repository Setup

### 3.1 Required secrets

Go to: **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|--------|-------|
| `HETZNER_HOST` | `<SERVER_IP>` |
| `HETZNER_USER` | `deploy` |
| `HETZNER_SSH_KEY` | Full content of your private SSH key (`cat ~/.ssh/id_ed25519`) |

> `GITHUB_TOKEN` is provided automatically — no extra secret needed for GHCR push.

### 3.2 Create a production environment (recommended)

GitHub repo → **Settings → Environments → New environment** → name it `production`.

This lets you add required reviewers before any push to `main` auto-deploys.

### 3.3 GHCR package visibility

After the first successful build, go to:  
**GitHub profile → Packages → blackstick → Package settings → Change visibility → Public**

This allows the server to pull the image without authentication. If you keep it private, generate a Personal Access Token with `read:packages` scope and store it on the server — then log in to GHCR manually once:

```bash
echo "<PAT>" | docker login ghcr.io -u shohrukhdev --password-stdin
```

---

## Part 4 — First Deployment (SSL Bootstrap)

This is a one-time manual process done before CI/CD takes over.

### 4.1 Copy infrastructure files to server

From your local machine:

```bash
scp docker-compose.prod.yml deploy@<SERVER_IP>:/opt/blackstick/
scp -r nginx/ deploy@<SERVER_IP>:/opt/blackstick/
```

### 4.2 Bootstrap SSL — HTTP-only phase

nginx cannot start with the HTTPS config until a certificate exists.  
We temporarily use the HTTP-only init config:

```bash
ssh deploy@<SERVER_IP>
cd /opt/blackstick

# Activate the HTTP-only config
mv nginx/conf.d/booket.conf nginx/conf.d/booket.conf.disabled
# booket-init.conf (HTTP only) is now the active config

# Pull the app image (trigger CI/CD first, or build manually)
docker compose -f docker-compose.prod.yml pull

# Start db, redis, web, nginx
docker compose -f docker-compose.prod.yml up -d db redis web nginx
```

### 4.3 Issue the SSL certificate

```bash
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email your@email.com \
  --agree-tos \
  --no-eff-email \
  -d booket.uz \
  -d www.booket.uz
```

### 4.4 Switch to HTTPS config

```bash
# Activate the full HTTPS + HTTP redirect config
mv nginx/conf.d/booket.conf.disabled nginx/conf.d/booket.conf
rm nginx/conf.d/booket-init.conf

# Reload nginx without downtime
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

Verify:

```bash
curl -I https://booket.uz
# Expected: HTTP/2 200
```

### 4.5 Start certbot auto-renewal

```bash
docker compose -f docker-compose.prod.yml up -d certbot
```

The certbot container checks for renewals every 12 hours and renews certs 30 days before expiry.

---

## Part 5 — Loading Initial Data

After first deploy, load demo fixtures:

```bash
docker exec blackstick_web python manage.py loaddata \
  booket/fixtures/providers.json \
  booket/fixtures/servers.json \
  booket/fixtures/service_types.json \
  booket/fixtures/services.json \
  booket/fixtures/provider_server.json \
  booket/fixtures/provider_server_services.json
```

See `booket/fixtures/README.md` for full instructions including user creation.

---

## Part 6 — Cron Jobs

```bash
# On server as deploy user
crontab -e
```

Add:

```cron
# Auto-resolve past appointments every 10 minutes
*/10 * * * * docker exec blackstick_web python manage.py complete_appointments >> /var/log/booket_cron.log 2>&1

# Daily database backup at 3 AM
0 3 * * * /opt/blackstick/backup.sh >> /var/log/booket_backup.log 2>&1
```

Create log files:

```bash
sudo touch /var/log/booket_cron.log /var/log/booket_backup.log
sudo chown deploy:deploy /var/log/booket_cron.log /var/log/booket_backup.log
```

---

## Part 7 — Database Backups

### When data can be lost

The PostgreSQL data lives in the Docker named volume `postgres_data` on the Hetzner disk.
Understanding which operations destroy it prevents accidents.

| Action | Data lost? | Notes |
|--------|-----------|-------|
| `docker compose -f docker-compose.prod.yml down` | **No** | Volumes survive a normal stop |
| `docker compose -f docker-compose.prod.yml up -d --no-deps web` | **No** | Only restarts the app container |
| `docker compose -f docker-compose.prod.yml down -v` | **YES — complete loss** | `-v` flag removes all named volumes |
| `docker volume rm blackstick_postgres_data` | **YES — complete loss** | Direct volume deletion |
| `docker system prune --volumes` | **YES — complete loss** | Prunes all unused volumes |
| `docker compose -f docker-compose.prod.yml pull && up` | **No** | Image update, volume untouched |
| Hetzner server **Rebuild** (re-image) | **YES — complete loss** | Wipes the disk; do not use Rebuild |
| Hetzner server **Delete** | **YES — complete loss** | Disk deleted with the server |
| Hetzner server **Resize** (vertical scale) | **No** | Disk is preserved during resize |
| Hetzner server **reboot** / power-cycle | **No** | Normal restart, volume intact |
| Redis container restart | **No** | Sessions lost (users logged out), no app data lost |
| Hetzner automatic server backup restore | Rolls back to backup point | Use only as last resort; restores the whole disk |

**Rule of thumb:** never pass `-v` to `docker compose down` in production, and never run `docker system prune` without first checking what volumes exist.

Backups are stored locally on the Hetzner disk and rotated to keep the last 7 days.  
Hetzner's automatic server backup (enabled in Part 1) provides an additional safety net.

```bash
cat > /opt/blackstick/backup.sh << 'EOF'
#!/bin/bash
set -e
BACKUP_DIR="/opt/backups"
DATE=$(date +%Y%m%d_%H%M%S)
FILE="${BACKUP_DIR}/blackstick_${DATE}.sql.gz"

docker exec blackstick_db pg_dump -U blackstick blackstick | gzip > "$FILE"

# Rotate: keep only the 7 most recent backups
ls -t "${BACKUP_DIR}"/blackstick_*.sql.gz | tail -n +8 | xargs -r rm

echo "Backup OK: $FILE"
EOF

chmod +x /opt/blackstick/backup.sh
```

Test it:

```bash
/opt/blackstick/backup.sh && ls -lh /opt/backups/
```

To restore from a backup:

```bash
gunzip -c /opt/backups/blackstick_YYYYMMDD_HHMMSS.sql.gz | docker exec -i blackstick_db psql -U blackstick blackstick
```

---

## Part 8 — Monitoring

### Container status

```bash
docker compose -f /opt/blackstick/docker-compose.prod.yml ps
```

### Live logs

```bash
# App
docker compose -f /opt/blackstick/docker-compose.prod.yml logs web -f

# Nginx access
docker compose -f /opt/blackstick/docker-compose.prod.yml logs nginx -f

# All containers
docker compose -f /opt/blackstick/docker-compose.prod.yml logs -f
```

### Hetzner built-in metrics

In Hetzner Console → `blackstick-prod` → **Metrics**: CPU, RAM, network, disk I/O are graphed with no setup.

Enable alerts: **Account → Notifications** — Hetzner emails you when the server becomes unreachable.

### Uptime monitoring (free, recommended)

1. Sign up at [uptimerobot.com](https://uptimerobot.com)
2. Add HTTP(S) monitor: `https://booket.uz`
3. Set alert contact email — notified within 5 minutes of downtime

---

## Part 9 — Day-2 Operations

### Disk usage

```bash
df -h
docker system df
ls -lh /opt/backups/
```

### Normal deploy

Push to `main`. GitHub Actions builds, pushes to GHCR, SSHs in and restarts only the web container.  
DB, Redis, and nginx keep running — no downtime for those services.

### Manual redeploy

```bash
ssh deploy@<SERVER_IP>
cd /opt/blackstick
docker compose -f docker-compose.prod.yml pull web
docker compose -f docker-compose.prod.yml up -d --no-deps web
```

### Django management commands

```bash
docker exec blackstick_web python manage.py <command>

# Examples:
docker exec blackstick_web python manage.py createsuperuser
docker exec -it blackstick_web python manage.py shell
docker exec blackstick_web python manage.py complete_appointments --days-back 30
```

### Scale workers

Edit `docker-compose.prod.yml`, increase `--workers` in the Gunicorn command (recommended: 2× CPU cores + 1):

```yaml
command: >
  gunicorn Blackstick.wsgi:application
    --bind 0.0.0.0:8000
    --workers 5
    --timeout 120
```

If CPU or RAM becomes the bottleneck, upgrade the server type in Hetzner Console (**Resize** tab) — takes ~2 minutes, data is preserved.

---

## Secrets Reference

| Where | Name | Description |
|-------|------|-------------|
| GitHub Secrets | `HETZNER_HOST` | Server IP address |
| GitHub Secrets | `HETZNER_USER` | SSH username (`deploy`) |
| GitHub Secrets | `HETZNER_SSH_KEY` | Private SSH key (full content) |
| Server `.env` | `SECRET_KEY` | Django secret key |
| Server `.env` | `FERNET_KEY` | Token encryption key |
| Server `.env` | `DB_PASSWORD` | PostgreSQL password |
| Server `.env` | `REDIS_URL` | `redis://redis:6379/1` |
| Server `.env` | `AWS_SES_USER_ACCESS_KEY_ID` | SES key for transactional email |
| Server `.env` | `AWS_SES_USER_SECRET_ACCESS_KEY` | SES secret for transactional email |
| Server `.env.db` | `POSTGRES_PASSWORD` | Must match `DB_PASSWORD` |
