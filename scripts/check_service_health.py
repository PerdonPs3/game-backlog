"""Check the deployed database-backed public readiness signal without secrets."""
import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check(base_url, attempts=3, opener=None, sleep=time.sleep):
    parsed = urlsplit(base_url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
        raise ValueError('Use an HTTPS application origin without credentials, query, or path.')
    if not 1 <= attempts <= 3:
        raise ValueError('Choose between one and three attempts.')
    opener = opener or build_opener(NoRedirects())
    for attempt in range(attempts):
        try:
            request = Request(base_url.rstrip('/') + '/community/member-count', headers={
                'Accept': 'application/json', 'Cache-Control': 'no-cache',
                'User-Agent': 'Vestigium-service-health/1.0'})
            with opener.open(request, timeout=15) as response:
                payload = json.loads(response.read(4096))
                if (response.status == 200 and isinstance(payload, dict)
                        and type(payload.get('count')) is int and payload['count'] >= 0):
                    return True
        except (HTTPError, URLError, OSError, ValueError, UnicodeError):
            pass
        if attempt + 1 < attempts:
            sleep(2 ** attempt)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base_url')
    args = parser.parse_args()
    try:
        healthy = check(args.base_url)
    except ValueError:
        print('Invalid configuration: expected a public HTTPS application origin.')
        return 2
    print('Database readiness: healthy.' if healthy else
          'Database readiness: unavailable. Check the deployment and Supabase project status.')
    return 0 if healthy else 1


if __name__ == '__main__':
    raise SystemExit(main())
