#!/usr/bin/env python3

# bookmarkthumbnailer
# Copyright (C) 2015 Ingo Ruhnke <grumbel@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import argparse
import logging
import json
import base64
import hashlib
import os
import subprocess
import concurrent.futures
import sqlite3
import time


def make_thumbnail(url, outfilename):
    if os.path.exists(outfilename) or os.path.exists(outfilename + ".error") :
        logging.info("skipping %s", outfilename)
    else:
        tmpfile = outfilename + ".part"

        logging.info("%s: processing", url)
        p = subprocess.Popen(
            ["wkhtmltoimage",
             "--quiet",
             "--format", "jpeg",
             "--quality", "80",
             "--load-error-handling", "abort",
             "--load-media-error-handling", "ignore",
             "--width", "1024",
             "--crop-w", "1024",
             # "--disable-smart-width",
             url,
             tmpfile],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
            )
        stdoutdata, stderrdata = p.communicate()
        if p.returncode == 0:
            os.rename(tmpfile, outfilename)
            logging.info("%s: success", outfilename)
        else:
            logging.error("%s: failed to process", outfilename)
            with open(outfilename + ".error", "wb") as fout:
                fout.write(b"stderr:\n")
                fout.write(stdoutdata)
                fout.write(b"\nstderr:\n")
                fout.write(stderrdata)


def collect_bookmarks(root, bookmarks):
    if root['type'] == 'folder':
        for child in root['children']:
            collect_bookmarks(child, bookmarks)
    elif root['type'] == 'url':
        bookmarks.append(root['url'])
    else:
        logging.warning("unknown type %s", root['type'])


def parse_args():
    parser = argparse.ArgumentParser(description='Webpage Thumbnailer')
    parser.add_argument('FILE', action='store', type=str, nargs=1,
                        help='File with URLs')
    parser.add_argument('-o', '--output', metavar='DIR', type=str, required=True,
                        help="output directory")

    return parser.parse_args()


def read_chrome_bookmarks(filename):
    with open(filename) as fin:
        data = json.load(fin)

    bookmarks = []
    collect_bookmarks(data['roots']['bookmark_bar'], bookmarks)
    return set(bookmarks)


def read_chrome_history(filename):
    urls = set()

    conn = sqlite3.connect(filename)
    c = conn.cursor()
    rows = c.execute('SELECT url FROM urls;')
    for url, in rows:
        urls.add(url)

    return urls


def generate_thumbnails(urls, output_directory):
    max_workers=2
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for idx, url in enumerate(urls):
            print("[{}/{}] Processing {}".format(idx, len(urls), url))

            # base64 doesn't work, runs into filename length limits
            # encode_url = base64.b64encode(url.encode('utf-8')).decode('utf-8')

            sha1 = hashlib.sha1()
            sha1.update(url.encode('utf-8'))
            encoded_url = sha1.hexdigest()

            futures.append(executor.submit(make_thumbnail,
                                           url,
                                           os.path.join(output_directory, encoded_url + ".jpg")))
            while executor._work_queue.qsize() == max_workers:
                time.sleep(0.1)

        for idx, f in enumerate(futures):
            print("[{}/{}] Completed".format(idx, len(futures)))
            print(f.result())


def main():
    args = parse_args()

    output_directory = args.output

    logging.basicConfig(level=logging.DEBUG)
    logging.info("Reading bookmarks...")

    # urls = read_chrome_bookmarks(args.FILE)
    urls = read_chrome_history(args.FILE[0])

    logging.info("%s urls found", len(urls))

    generate_thumbnails(sorted(urls), output_directory)


if __name__ == "__main__":
    main()


# EOF #
