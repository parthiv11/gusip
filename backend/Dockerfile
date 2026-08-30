FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ffmpeg tesseract-ocr libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# CPU wheels only. `pip install ultralytics` on amd64 otherwise pulls CUDA torch (~6GB).
RUN grep -v '^ultralytics' requirements.txt > /tmp/req.txt \
 && pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r /tmp/req.txt \
 && pip install --no-cache-dir ultralytics==8.3.70 --no-deps \
 && pip install --no-cache-dir opencv-python-headless matplotlib pandas seaborn psutil py-cpuinfo ultralytics-thop scipy tqdm requests

COPY . .

RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
