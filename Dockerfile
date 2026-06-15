FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY requirements.txt .
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt
COPY . .
RUN mkdir -p /app/instance && chown -R appuser:appuser /app
USER appuser
EXPOSE 2331
CMD ["waitress-serve", "--host=0.0.0.0", "--port=2331", "--call", "link_analytics:create_app"]
