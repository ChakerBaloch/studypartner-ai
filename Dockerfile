FROM python:3.11-slim

WORKDIR /app

# Copy full source for proper package installation
COPY pyproject.toml .
COPY src/ src/

# Install the package (server-only deps, no pyobjc)
RUN pip install --no-cache-dir \
    fastapi>=0.110 \
    uvicorn[standard]>=0.27 \
    google-genai>=1.0 \
    google-adk>=1.0 \
    pydantic>=2.0 \
    python-multipart>=0.0.9 \
    websockets>=12.0

# Install the package itself so module imports work
ENV PYTHONPATH=/app/src

EXPOSE 8080

CMD ["uvicorn", "studypartner.server.main:app", "--host", "0.0.0.0", "--port", "8080"]
