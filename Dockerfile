FROM python:3.7-alpine

WORKDIR /usr/src/app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT [ "python", "./bin/generate_report.py" ]
