# <img src="app/static/whisp-logo.svg" width="48" height="48" style="vertical-align: middle;"> Whisp

Whisp is a lightweight, self-hosted secret sharing application built with the **PETAL Stack** (Python, Alpine.js, Tailwind CSS, Linux). It allows you to share encrypted strings or files with a temporary, unique link that expires after a set duration or after being accessed once.

## Features
- **Zero-Knowledge Encryption**: Secrets are encrypted in the browser using the Web Crypto API (AES-GCM 256-bit). The server never sees the plaintext or the decryption key.
- **RAM-Only File Storage**: Files are stored in a temporary `tmpfs` volume in RAM, never touching the physical disk.
- **Encryption at Rest**: Files are encrypted on the server with a unique, transient key before being stored in memory.
- **One-Time Access**: Whisps are automatically deleted after the first access.
- **Expiration (TTL)**: Set a duration for how long the secret should be available (1 minute to 1 week).
- **Password Protection**: Add an extra layer of security with a custom password.
- **File Support**: Share files up to 10MB securely.
- **Lightweight**: Built with FastAPI and SQLite for minimal resource usage.
- **Secure**: Multi-stage Docker build, non-root user, async file operations, and sanitized inputs.

## Tech Stack
- **Backend**: Python 3.11 (FastAPI + SQLAlchemy)
- **Database**: SQLite (async with aiosqlite)
- **Encryption**: 
  - Client-side: Web Crypto API (AES-GCM)
  - Server-side: Cryptography (Fernet/AES)
- **Frontend**: PETAL Stack (Python + Alpine.js + Tailwind CSS + Linux)
- **Infrastructure**: Docker / Docker Compose

## Quick Start

### Docker (Recommended)
```bash
mkdir -p data && chown -R 1000:1000 data
docker-compose up -d
```

### Production Deployment (Traefik + Docker Compose)
To use the pre-built image from GitHub Container Registry with a reverse proxy like Traefik:

```yaml
# docker-compose.yml
services:
  whisp:
    image: ghcr.io/adam-benyekkou/whisp-secret:latest
    container_name: whisp
    restart: unless-stopped
    networks:
      - proxy-network
    environment:
      - DATABASE_URL=sqlite+aiosqlite:////app/data/whisp.db
      - STORAGE_DIR=/app/data/storage
      - DEBUG=false
    volumes:
      - ./data:/app/data
    tmpfs:
      # Secure ephemeral storage in RAM for encrypted file fragments
      - /app/data/storage:size=100M,mode=1777
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=proxy-network"
      - "traefik.http.routers.whisp.rule=Host(`whisp.yourdomain.com`)"
      - "traefik.http.routers.whisp.entrypoints=websecure"
      - "traefik.http.routers.whisp.tls.certresolver=myresolver"
      - "traefik.http.services.whisp.loadbalancer.server.port=8000"

networks:
  proxy-network:
    external: true
```

#### Setup Persistence
```bash
mkdir -p data && chown -R 1000:1000 data
docker compose up -d
```

### Manual Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the server:
   ```bash
   uvicorn app.main:app --reload
   ```

## Security Features
- **Client-side encryption** (AES-GCM with random IVs) for text secrets.
- **Server-side encryption** for files using unique per-file keys.
- **RAM-only storage** (`tmpfs`) ensures files are never written to the persistent disk.
- **Rate Limiting** to prevent brute-force and DoS attacks.
- **Streaming Uploads** to handle files efficiently without memory exhaustion.
- Server receives only encrypted payloads or encrypts streams immediately.
- Decryption key transmitted via URL fragment (never sent to server).
- One-time access with automatic deletion (database record removed immediately on access).
- File size validation (10MB limit).
- Path traversal protection.
- Non-root Docker container.
- CORS configuration.
- Password hashing with bcrypt (SHA-256 pre-hashing).

## Configuration
Copy `.env.example` to `.env` and configure:
- `DATABASE_URL`: Database connection string
- `DEBUG`: Enable/disable debug mode
- `MAX_FILE_SIZE`: Maximum file upload size in bytes

## Testing

### E2E Tests with Playwright

The project includes comprehensive end-to-end tests that verify:
- Creating and retrieving text whisps
- Password-protected whisps
- One-time access (deletion after first view)
- Expiration handling
- UI functionality

#### Setup
```bash
npm install
npx playwright install chromium
```

#### Run Tests
```bash
# Make sure the app is running first
docker-compose up -d --build

# Run backend unit tests inside the container
docker exec whisp-whisp-1 python -m pytest tests/test_backend.py

# Run E2E tests (requires local node/playwright setup)
npm install
npx playwright install chromium
npx playwright test
```

#### Test Coverage
- ✅ Create text whisp and decrypt
- ✅ Password protection
- ✅ One-time access deletion
- ✅ TTL options
- ✅ UI rendering
- ✅ Clipboard functionality

## License
MIT
