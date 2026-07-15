from functools import partial
import http.server
from pathlib import Path
import select
import socketserver
import sys
import threading
import time
import webbrowser


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True
    allow_reuse_port = True


PORT = 8123
DIR = Path(__file__).parent
INDEX_TEMPLATE = DIR / "index.template.html"
INDEX = DIR / "index.html"


def main() -> None:
    data = ""
    if select.select([sys.stdin], [], [], 0)[0]:
        data = sys.stdin.read().strip()
    if not data:
        sys.exit(
            "Error: Run by piping in output of EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON) - use pbpaste on Mac"
        )

    INDEX.write_text(INDEX_TEMPLATE.read_text().replace("{{ plan }}", data))

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=DIR)
    httpd = ReusableTCPServer(("localhost", PORT), handler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    url = f"http://localhost:{PORT}"
    webbrowser.get().open(url, new=2)
    server_thread.join()


if __name__ == "__main__":
    main()
