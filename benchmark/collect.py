"""Sample cumulative Docker counters using the local Engine API (no dependencies)."""
import datetime
import http.client
import json
import signal
import socket
import sys
import time


class DockerConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        self.sock.connect('/var/run/docker.sock')


def request(path):
    connection = DockerConnection('localhost', timeout=10)
    try:
        connection.request('GET', path)
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f'Docker API {path}: {response.status}')
        return json.load(response)
    finally:
        connection.close()


def main():
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    containers = sys.argv[1:]
    # Take a final sample after SIGTERM, so CPU deltas bracket the workload.
    while True:
        for container in containers:
            stats = request(f'/containers/{container}/stats?stream=false&one-shot=true')
            print(json.dumps({
                'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'container': container,
                'cpu_seconds': stats['cpu_stats']['cpu_usage']['total_usage'] / 1e9,
                'memory_bytes': stats.get('memory_stats', {}).get('usage', 0),
                'networks': stats.get('networks', {}),
            }), flush=True)
        if not running:
            break
        time.sleep(1)


if __name__ == '__main__':
    main()
