FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
RUN apt-get update && apt-get install -y nodejs npm
COPY exyt-control /app/exyt-control
RUN cd exyt-control && npm install
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]