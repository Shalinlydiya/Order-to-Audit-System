FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt . 
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV DB_PATH=/data/factory.db
CMD ["gunicorn","-w","1","--threads","4","-b","0.0.0.0:8000","app:app"]
