FROM python:3.14-slim-trixie
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./app /code/app
CMD ["gunicorn", "--bind=0.0.0.0:80", "app.main:app"]
