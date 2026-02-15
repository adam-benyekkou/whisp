# <img src="app/static/whisp-logo.svg" width="48" height="48" style="vertical-align: middle;"> Whisp

Whisp is a lightweight, self-hosted secret sharing application. It allows you to share encrypted strings or files with a temporary, unique link that expires after a set duration or after being accessed once.

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
- **Frontend**: Vanilla JS + Tailwind CSS (Glassmorphism UI)
- **Infrastructure**: Docker / Docker Compose

## Quick Start

### Docker (Recommended)
```bash
docker-compose up -d
```

### Production Deployment (Pre-built Image)
To use the pre-built image from GitHub Container Registry:

```yaml
# docker-compose.yml
services:
  whisp:
    image: ghcr.io/adam-benyekkou/whisp:latest
    ports:
      - "8000:8000"
    tmpfs:
      - /app/app/storage/files:size=100M,mode=1777
    volumes:
      - whisp_data:/app/data
    environment:
      - DATABASE_URL=sqlite+aiosqlite:////app/data/whisp.db
    restart: unless-stopped

volumes:
  whisp_data:
```

Access the app at **http://localhost:8000**

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
docker-compose up -d

# Run tests
npm test

# Run with UI
npm run test:ui

# Run in headed mode (see browser)
npm run test:headed

# Debug mode
npm run test:debug
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
