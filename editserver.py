#!/usr/bin/env python

# Copyright (C) 2009  David Hilley <davidhi@cc.gatech.edu>
# Copyright (C) 2010  Matt DeVuyst <mdevuyst@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import BaseHTTPServer
import logging
import optparse
import os
import platform
import re
import stat
import subprocess
import sys
import tempfile
import time

DEFAULT_PORT = 9292
DEFAULT_EDITOR = "rgvim,-f"

logging.basicConfig(
    format="%(asctime)s - %(message)s",
    level=logging.INFO)

TEMP_HAS_DELETE = platform.python_version_tuple()[:2] >= ("2", "6")
if not TEMP_HAS_DELETE:
    print "Handling lack of delete for NamedTemporaryFile:", TEMP_HAS_DELETE

_processes = {}

class Handler(BaseHTTPServer.BaseHTTPRequestHandler):
    """Handler for an edit-server.
    """
    editor = DEFAULT_EDITOR
    processes = _processes

    def do_GET(self):
        """Handle a GET-request.
        """
        if self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("edit-server is running.\n")
        else:
            self.send_error(404, "GET Not Found: %s" % self.path)

    def do_POST(self):
        """Handle a POST-request.
        """
        try:
            clength = 0
            cl = self.headers.getheader("Content-Length")

            if cl != None:
                clength = int(cl)
            else:
                self.send_response(411)
                self.end_headers()
                return

            body = self.rfile.read(clength)
            print body

            l = [s for s in self.path.split("/") if s]
            print l

            existing_file = self.headers.getheader("X-File")

            # write text into file
            if not existing_file or existing_file == "undefined":
                existing = False
                url = self.headers.getheader("X-Url")
                print "url:", url
                prefix = "chrome_"
                if url:
                    prefix += re.sub("[^.\w]", "_", re.sub("^.*?//","",url))
                prefix += "_"
                if TEMP_HAS_DELETE==True:
                    f = tempfile.NamedTemporaryFile(
                            delete=False, prefix=prefix, suffix=".txt")
                    fname = f.name
                else:
                    tf = tempfile.mkstemp(prefix=prefix, suffix=".txt")
                    f = os.fdopen(tf[0],"w")
                    fname = tf[1]
                print "Opening new file ", fname
            else:
                existing = True
                p = self.processes[existing_file]
                print "Opening existing file ", existing_file
                f = open(existing_file, "w")
                fname = existing_file

            f.write(body)
            f.close()
            last_mod_time = os.stat(fname)[stat.ST_MTIME]

            if not existing:
                # spawn editor...
                print "Spawning editor... ", fname

                cmd = self.editor.split(",")
                cmd.append(fname)
                print cmd
                p = subprocess.Popen(cmd, close_fds=True)
                self.processes[fname] = p

            saved = False
            rc = None
            while (True):
                time.sleep(1)
                rc = p.poll()
                if rc != None: break
                mod_time = os.stat(fname)[stat.ST_MTIME]
                if mod_time != last_mod_time:
                    print "new mod time:", mod_time, " last:", last_mod_time
                    last_mod_time = mod_time
                    saved = True
                if saved: break

            if saved or not rc:
                self.send_response(200)

                f = file(fname, "r")
                s = f.read()
                f.close()
            else:
                if rc > 0:
                    msg = "text editor returned %d" % rc
                elif rc < 0:
                    msg = "text editor died on signal %d" % -rc
                self.send_error(404, msg)

            if saved:
                self.send_header("X-Open", "true")
            else:
                try:
                    os.unlink(fname)
                except :
                    print "Unable to unlink:", fname
                    pass

            self.send_header("X-File", fname)
            self.end_headers()
            self.wfile.write(s)
        except :
            print "Error: ", sys.exc_info()[0]
            self.send_error(404, "Not Found: %s" % self.path)


def runServer(editor=DEFAULT_EDITOR, port=DEFAULT_PORT):
    """Run an edit-server.
    """
    try:
        Handler.editor = editor

        server = BaseHTTPServer.HTTPServer(("localhost", port), Handler)
        server.table = {}
        server.serve_forever()
    except KeyboardInterrupt:
        server.socket.close()

if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option(
        "-p", "--port",
        type="int",
        dest="port",
        default=DEFAULT_PORT,
        help="port number to listen on (default: " + str(DEFAULT_PORT) + ")")
    parser.add_option(
        "-e", "--editor",
        dest="editor",
        default=DEFAULT_EDITOR,
        help='text editor to spawn (default: "' + DEFAULT_EDITOR + '")')
    options = parser.parse_args()[0]

    runServer(editor=options.editor, port=options.port)
