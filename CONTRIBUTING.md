# Contributing to Whisp

## Local Development (Manual Setup)

While Docker is the recommended way to run Whisp, you can set it up manually for development purposes.

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configuration**:
    Create a `.env` file based on `.env.example`.

3.  **Run the Server**:
    ```bash
    uvicorn app.main:app --reload
    ```

## Security Checks
We use `bandit`, `safety`, and `trivy` for security auditing.

To run locally:
```bash
pip install bandit safety
bandit -r app -x tests
safety check
```

## Docker Build
To test the production build locally:
```bash
docker build -t whisp-secret:latest .
```
