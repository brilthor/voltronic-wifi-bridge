FROM python:3.11

WORKDIR /voltronic_wifi_bridge/
COPY . /voltronic_wifi_bridge/
RUN pip install -e .

CMD ["voltronic-wifi-bridge", "-h"]