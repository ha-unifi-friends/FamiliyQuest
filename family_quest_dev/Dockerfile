ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /app/requirements.txt

COPY app/ /app/
COPY packs/ /app/packs/
COPY config.yaml /app/config.yaml
COPY CHANGELOG.md /app/CHANGELOG.md
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
