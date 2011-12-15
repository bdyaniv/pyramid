import optparse
import sys
import textwrap

from pyramid.compat import url_quote
from pyramid.request import Request
from pyramid.paster import get_app

def main(argv=sys.argv, quiet=False):
    command = PRequestCommand(argv, quiet)
    return command.run()

class PRequestCommand(object):
    description = """\
    Run a request for the described application.

    This command makes an artifical request to a web application that uses a
    PasteDeploy (.ini) configuration file for the server and application.

    Use "prequest config.ini /path" to request "/path".  Use "prequest
    config.ini /path --method=post < data" to do a POST with the given
    request body.

    If the path is relative (doesn't begin with "/") it is interpreted as
    relative to "/".

    The variable "environ['paste.command_request']" will be set to "True" in
    the request's WSGI environment, so your application can distinguish these
    calls from normal requests.

    Note that you can pass options besides the options listed here; any
    unknown options will be passed to the application in
    "environ['QUERY_STRING']"
    """
    usage = "usage: %prog config_file path_info [args/options]"
    parser = optparse.OptionParser(
        usage=usage,
        description=textwrap.dedent(description)
        )
    parser.add_option(
        '-n', '--app-name',
        dest='app_name',
        metavar= 'NAME',
        help="Load the named application from the config file (default 'main')",
        type="string",
        )
    parser.add_option(
        '--header',
        dest='headers',
        metavar='NAME:VALUE',
        type='string',
        action='append',
        help="Header to add to request (you can use this option multiple times)"
        )
    parser.add_option(
        '-d', '--display-headers',
        dest='display_headers',
        action='store_true',
        help='Display status and headers before the response body'
        )
    parser.add_option(
        '-m', '--method',
        dest='method',
        choices=['GET', 'HEAD', 'POST', 'DELETE'],
        type='choice',
        help='Request method type (GET, POST, DELETE)',
        )

    get_app = staticmethod(get_app)
    stdin = sys.stdin

    def __init__(self, argv, quiet=False):
        self.quiet = quiet
        self.options, self.args = self.parser.parse_args(argv[1:])

    def out(self, msg): # pragma: no cover
        if not self.quiet:
            print(msg)

    def run(self):
        if not len(self.args) >= 2:
            self.out('You must provide at least two arguments')
            return 2
        app_spec = self.args[0]
        path = self.args[1]
        if not path.startswith('/'):
            path = '/' + path 

        headers = {}
        if self.options.headers:
            for item in self.options.headers:
                if ':' not in item:
                    self.out(
                        "Bad --header=%s option, value must be in the form "
                        "'name:value'" % item)
                    return 2
                name, value = item.split(':', 1)
                headers[name] = value.strip()

        app = self.get_app(app_spec, self.options.app_name)
        request_method = (self.options.method or 'GET').upper()

        qs = []
        for item in self.args[2:]:
            if '=' in item:
                k, v = item.split('=', 1)
                item = url_quote(k) + '=' + url_quote(v)
            else:
                item = url_quote(item)
            qs.append(item)
        qs = '&'.join(qs)
        
        environ = {
            'REQUEST_METHOD': request_method,
            'SCRIPT_NAME': '',           # may be empty if app is at the root
            'PATH_INFO': path,             # may be empty if at root of app
            'SERVER_NAME': 'localhost',  # always mandatory
            'SERVER_PORT': '80',         # always mandatory 
            'SERVER_PROTOCOL': 'HTTP/1.0',
            'CONTENT_TYPE': 'text/plain',
            'wsgi.run_once': True,
            'wsgi.multithread': False,
            'wsgi.multiprocess': False,
            'wsgi.errors': sys.stderr,
            'wsgi.url_scheme': 'http',
            'wsgi.version': (1, 0),
            'QUERY_STRING': qs,
            'HTTP_ACCEPT': 'text/plain;q=1.0, */*;q=0.1',
            'paste.command_request': True,
            }

        if request_method == 'POST':
            environ['wsgi.input'] = self.stdin
            environ['CONTENT_LENGTH'] = '-1'

        for name, value in headers.items():
            if name.lower() == 'content-type':
                name = 'CONTENT_TYPE'
            else:
                name = 'HTTP_'+name.upper().replace('-', '_')
            environ[name] = value

        request = Request.blank(path, environ=environ)
        response = request.get_response(app)
        if self.options.display_headers:
            self.out(response.status)
            for name, value in response.headerlist:
                self.out('%s: %s' % (name, value))
        self.out(response.ubody)
        return 0
