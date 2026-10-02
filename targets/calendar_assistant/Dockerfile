FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY AgentCard.json prompt.txt benign_tasks.json ./
COPY src/main.py ./src/main.py
EXPOSE 8000
CMD ["python", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]
