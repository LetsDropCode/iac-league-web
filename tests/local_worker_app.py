"""Test-only WSGI wrapper. Not the production or staging start target."""
import os
from app import app, get_tables


def application(environ, start_response):
    def respond(status, headers, exc_info=None):
        headers.append(('X-Test-Worker-Pid', str(os.getpid())))
        headers.append(('X-Test-Points', str(int(get_tables()[0]['Total Points'].sum()))))
        return start_response(status, headers, exc_info)
    return app(environ, respond)
