# https://github.com/deepnox-io/docker-python-ta-lib/commit/7f3104467513a49011d395b2d5e9cdebc998bf94#diff-1dd728afd29d8d19958ed81d87cc6151661a86ae53622dcadaac8def63f6f1e0R1
FROM deepnox/python-ta-lib:0.4.21_python3.9.7-alpine3.14

COPY requirements.txt /app
WORKDIR /app

RUN pip3 install -r requirements.txt

CMD ["python3"]
