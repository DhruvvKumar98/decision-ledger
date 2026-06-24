FROM python:3.12-slim

# Create non-root user before anything else
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /srv

# Install dependencies as root, then switch
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./api/

# Hand ownership to appuser
RUN chown -R appuser:appuser /srv

USER appuser

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
