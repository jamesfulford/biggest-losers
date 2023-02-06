FROM python:3.9-alpine

# install pandas
RUN apk add --no-cache --update \
    python3 python3-dev gcc \
    gfortran musl-dev g++ \
    libffi-dev openssl-dev \
    libxml2 libxml2-dev \
    libxslt libxslt-dev \
    libjpeg-turbo-dev zlib-dev

RUN pip install --upgrade cython
RUN pip install --upgrade pip
RUN pip install numpy

RUN mkdir -p /app
WORKDIR /app
COPY requirements.txt /app
RUN pip3 install -r requirements.txt

CMD ["python3"]
