FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

WORKDIR /app/backend

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "run:app"]