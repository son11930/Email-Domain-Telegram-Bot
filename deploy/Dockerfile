FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY pyproject.toml README.md requirements.lock.txt ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade "pip>=26.2" && pip install --no-cache-dir -r requirements.lock.txt && pip install --no-cache-dir .
USER 10001:10001
EXPOSE 8001
CMD ["team-mail", "web"]
