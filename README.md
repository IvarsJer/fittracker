# FitTracker 🏋️

A self-hosted fitness & workout tracker. Built with Flask + PostgreSQL + vanilla JS, served via Nginx — all containerized.

---

## Stack

| Layer     | Tech                     |
|-----------|--------------------------|
| Frontend  | HTML / CSS / JS + Nginx  |
| Backend   | Python / Flask + Gunicorn|
| Database  | PostgreSQL 16            |
| Container | Docker Compose           |

---

## Quick Start

### 1. Prerequisites
- Docker + Docker Compose installed
- (Optional) Tailscale installed on the host

### 2. (Recommended) Change the DB password

Edit `docker-compose.yml` and replace `fitpass` in both:
```yaml
POSTGRES_PASSWORD: your_secure_password
DATABASE_URL: postgresql://fituser:your_secure_password@db:5432/fittracker
```

### 3. Build & run

```bash
docker compose up -d --build
```

First startup takes ~60 seconds while the DB initialises and exercises are seeded.

Open **http://localhost:3000** in your browser.

### 4. Useful commands

```bash
# View logs
docker compose logs -f

# Stop everything
docker compose down

# Stop and wipe the database (careful!)
docker compose down -v

# Rebuild after code changes
docker compose up -d --build
```

---

## Tailscale Access

Once the stack is running you can access it from **any device on your Tailscale mesh**:

1. Make sure Tailscale is running on the host machine:
   ```bash
   tailscale status
   ```

2. Note your machine's Tailscale IP (looks like `100.x.x.x`):
   ```bash
   tailscale ip -4
   ```

3. From any other device on your Tailscale network, open:
   ```
   http://100.x.x.x:3000
   ```

4. **(Optional) Set a Tailscale hostname** for a nicer URL.
   In your Tailscale admin panel (admin.tailscale.com → Machines) you can assign a hostname like `fittracker`, then access it as:
   ```
   http://fittracker:3000
   ```
   Or enable **MagicDNS** in the Tailscale admin panel and it resolves automatically across all your devices.

5. **(Optional) Serve on port 80** — edit `docker-compose.yml`:
   ```yaml
   ports:
     - "80:80"
   ```
   Then access it at just `http://fittracker` or `http://100.x.x.x`.

---

## Data Backup

PostgreSQL data is stored in a named Docker volume (`fittracker-pgdata`).

### Backup
```bash
docker exec fittracker-db pg_dump -U fituser fittracker > backup_$(date +%Y%m%d).sql
```

### Restore
```bash
cat backup_20240101.sql | docker exec -i fittracker-db psql -U fituser -d fittracker
```

---

## Features

- **Dashboard** — total workouts, current streak, volume chart, category mix, PRs
- **Log Workout** — add sets for any exercise (strength, bodyweight, cardio, custom)
- **History** — browse past workouts, click to see full set breakdown
- **Progress** — per-exercise max weight & volume over time charts
- **Body Weight** — log daily weight, 90-day trend chart
- **Exercise Library** — add / delete exercises, filter by category

---

## Customisation

- Add exercises via the **Exercise Library** page or directly in the DB
- Change port in `docker-compose.yml` → `ports: "YOURPORT:80"`
- Add HTTPS via a Tailscale HTTPS certificate or a local reverse proxy (Caddy/Traefik)
