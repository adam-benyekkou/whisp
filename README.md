# <img src="app/static/whisp-logo.svg" width="48" height="48" style="vertical-align: middle;"> Whisp

Whisp is a lightweight, self-hosted secret sharing application built with the **PETAL Stack** (Python, Alpine.js, Tailwind CSS, Linux). It allows you to share encrypted strings or files with a temporary, unique link that expires after a set duration or after being accessed once.

### [Live Demo](https://whisp.cavydev.com/)

## Security Architecture
Whisp is designed with a "security-first" mindset, ensuring that your data remains private and ephemeral.

- **Zero-Knowledge Encryption**: Secrets are encrypted in the browser using the Web Crypto API (AES-GCM 256-bit). The server never receives the plaintext or the decryption key.
- **Encryption at Rest**: Files are encrypted on the server with a unique, transient key before storage.
- **RAM-Only File Storage**: Uploaded artifacts are stored in a temporary `tmpfs` volume in RAM, ensuring they never touch the physical disk.
- **One-Time Access (Burn-on-Read)**: Whisps are automatically incinerated from both the database and storage immediately after the first access.
- **Rate Limiting & Hashing**: Protection against brute-force attacks via `slowapi` and secure password hashing using `bcrypt` (with SHA-256 pre-hashing).
- **Secure Infrastructure**: Multi-stage Docker builds, non-root execution, and sanitized async file operations.

## Tech Stack
- **Backend**: Python 3.11 (FastAPI + SQLAlchemy)
- **Database**: SQLite (async with aiosqlite)
- **Frontend**: PETAL Stack (Alpine.js + Tailwind CSS)
- **Interactions**: Web Crypto API (Client-side AES-GCM)

## Deployment

The recommended way to deploy Whisp is using **Docker Compose**.

1.  **Prepare the Environment**:
    ```bash
    mkdir -p data && chown -R 1000:1000 data
    ```

2.  **Create your `docker-compose.yml`**:
    ```yaml
    services:
      whisp:
        image: ghcr.io/adam-benyekkou/whisp-secret:latest
        container_name: whisp
        restart: unless-stopped
        ports:
          - "8000:8000"
        environment:
          - DATABASE_URL=sqlite+aiosqlite:////app/data/whisp.db
          - STORAGE_DIR=/app/data/storage
          - DEBUG=false
        volumes:
          - ./data:/app/data
        tmpfs:
          - /app/data/storage:size=100M,mode=1777
    ```

3.  **Launch**:
    ```bash
    docker compose up -d
    ```

## Configuration
Copy `.env.example` to `.env` to customize your installation:
- `DATABASE_URL`: Database connection string.
- `DEBUG`: Set to `false` for production.
- `MAX_FILE_SIZE`: Maximum file upload size in bytes (Default: 10MB).

## Testing

Whisp includes a comprehensive Playwright E2E suite and Pytest backend units.

```bash
# Run backend unit tests inside the container
docker exec whisp python -m pytest tests/test_backend.py

# Run E2E tests (requires local node/playwright setup)
npm install && npx playwright install chromium
npx playwright test
```

---

For local development and manual setup instructions, please refer to [CONTRIBUTING.md](CONTRIBUTING.md).

## License
MIT

