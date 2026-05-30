FROM python:3.12-slim

WORKDIR /app

# Install Docker CLI for L2 sandbox execution
RUN apt-get update && apt-get install -y docker.io && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY commitguard_env/ commitguard_env/
COPY data/ data/
COPY configs/ configs/
COPY server/ server/

RUN pip install -e .

EXPOSE 7860

CMD ["uvicorn", "commitguard_env.server:app", "--host", "0.0.0.0", "--port", "7860"]
