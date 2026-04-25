FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY commitguard_env /app/commitguard_env
COPY data /app/data
COPY cwe_keywords.json /app/

RUN pip install --no-cache-dir -U pip setuptools wheel \
  && pip install --no-cache-dir .

EXPOSE 8000

CMD ["python", "-m", "commitguard_env.server"]

