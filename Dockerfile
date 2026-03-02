FROM python:3.11-slim

WORKDIR /app

# Install only server dependencies
COPY pyproject.toml .
COPY src/studypartner/server/ src/studypartner/server/
COPY src/studypartner/shared/ src/studypartner/shared/
COPY src/studypartner/__init__.py src/studypartner/__init__.py

# Install minimal dependencies for the server (no pyobjc — macOS only)
RUN pip install --no-cache-dir \
    fastapi>=0.110 \
    uvicorn[standard]>=0.27 \
    google-genai>=1.0 \
    pydantic>=2.0 \
    python-multipart>=0.0.9

EXPOSE 8080

CMD ["uvicorn", "studypartner.server.main:app", "--host", "0.0.0.0", "--port", "8080"]
