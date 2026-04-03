FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for agent-search-tool channels
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent runner
COPY agent_runner.py /app/agent_runner.py

# Shared directory for SOUL.md, RULES.md, AGENTS.md, INSTRUCTIONS.md
RUN mkdir -p /app/shared

# Default command
CMD ["python", "agent_runner.py"]
