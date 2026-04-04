FROM python:3.12-slim

WORKDIR /app

# Install agent runtime dependencies
RUN pip install --no-cache-dir \
    "anthropic>=0.49.0" \
    "httpx>=0.27.0,<0.29.0" \
    openai==1.45.0 \
    redis==5.0.8 \
    asyncpg==0.29.0 \
    pyyaml==6.0.2 \
    python-dotenv==1.0.1

COPY agent_runner.py .

CMD ["python", "agent_runner.py"]
