#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Slowmo
simple time based web scraping script. 

uses GIT command line interface to archive data changes over time.
"""

import os
import time
import json
import argparse
import threading
import subprocess
import hashlib
import configparser


import requests as rq
from urllib3.exceptions import ReadTimeoutError
from bs4 import BeautifulSoup as bs


# Import Configuration from 'config.ini'.
config = configparser.ConfigParser()
config.read("config.ini")

CURRENT_PATH = os.getcwd()  # The current folder.
FILES_DIRNAME = config["GIT"]["DIR"]  # The name of the folder where we store git files.
FILES_DIR = os.path.join(CURRENT_PATH, FILES_DIRNAME)  # The full path to that folder.
MAX_THREADS = int(config["SCRIPT"]["MAX_THREADS"])  # The maximum number of threads.


parser = argparse.ArgumentParser()
parser.add_argument(
    "--reset", action="store_true", help=" remove local git repository and files."
)  # Adds --reset to command arguments.


get_time = lambda: time.strftime("%H:%M:%S", time.localtime())  # Gets the locale time.


def exec_cmd(
    command: str, _cwd: str = FILES_DIR, doPrint: bool = True
) -> subprocess.CompletedProcess:
    """Executes a command and eventually prints its result."""
    cmd_result = subprocess.run(
        [command],
        shell=True,
        cwd=_cwd,
        capture_output=True,
    )  # Executes the command and gets its result.

    # Displaying command results on console if doPrint parameters equals True.
    if doPrint:
        if cmd_result.returncode == 0:  # If there is no errors.
            print(  # Print the standard input
                "\033[1;90m[%s] \033[0;90m%s\033[0m"
                % (get_time(), cmd_result.stdout.decode("utf-8")),
            )
        else:  # Else, print the standard error input.
            print(
                "\033[1;91m[%s] \033[0;90m%s\033[0m"
                % (get_time(), cmd_result.stderr.decode("utf-8")),
            )

    return cmd_result


def reset_files() -> None:
    """Removes local git repository and files."""
    try:
        # Removes all files in the folder FIL_DIR.
        for root, dirs, files in os.walk(FILES_DIR, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))

    except OSError:
        pass

    else:
        print("Removed all git files.\n")

    finally:
        return


def process_request(request: dict) -> None:
    """ """
    try:
        res = rq.get(
            request["url"],
            data=request["body"],
            headers=request["headers"],
            timeout=float(config["REQUESTS"]["TIMEOUT"]),
        )  # Sends get request.

    except (
        rq.exceptions.Timeout,
        TimeoutError,
        ReadTimeoutError,
        rq.exceptions.ConnectionError,
    ):
        # If request has timed out.
        print(
            "\033[91m[%s] Request to %s has timed out.\033[0m"
            % (get_time(), request["url"])
        )

    else:

        if res.status_code == 200:
            # If request HTTP status is 200.

            print(
                "[%s]  \033[1;32m200\033[0m  %s" % (get_time(), request["url"])
            )  # Console display.

            soup = bs(res.content, "html.parser")  # Format html.

            # Remove style and script tags.
            [data.decompose() for data in soup(["style", "script"])]

            filename = "%s.html" % (
                hashlib.md5(request["url"].encode("utf-8")).hexdigest()
                if not "name" in request or len(request["name"]) < 3
                else request["name"]
            )  # filename : "name" attribute if it is defined in 'request.json',
            # else md5 hash of the request url.

            try:
                # Overwrites the file.
                file = open(os.path.join(FILES_DIR, filename), "w")
                file.write(str(soup))
                file.close()

                # execute "git add" command.
                exec_cmd(
                    "git add %s" % (filename),
                    doPrint=False,
                )

            except IOError:
                pass
        else:
            print(res.status_code)
    return


if __name__ == "__main__":

    print("\n\033[1mSlowmo\033[0m\n")

    args = parser.parse_args()  # Command arguments

    if not os.path.isdir(FILES_DIR):
        try:
            os.makedirs(FILES_DIR)
            print('Created "%s" folder.' % FILES_DIRNAME)
        except OSError:
            pass

    if args.reset:
        reset_files()

    # Running git init in an existing repository is safe.
    # It will not overwrite things that are already there.
    exec_cmd("git init")

    if exec_cmd("git status", doPrint=False).returncode == 0:
        # If "git status" command doesnt returns any error.
        print("Git is OK. \n")
    else:  # else, end script.
        exit()

    threads = [None] * MAX_THREADS

    # Loads 'request.json' data.
    f = open("requests.json")
    requests = json.load(f)

    try:

        while True:

            for idx, request in enumerate(
                requests
            ):  # For each requests in 'request.json'.

                time.sleep(
                    0.0 if idx == 0 else float(config["REQUESTS"]["EACH_INTERVAL"])
                )  # Waits EACH_INTERVAL seconds.

                thread_index = idx % MAX_THREADS  # thread index

                if idx > MAX_THREADS:
                    threads[thread_index].join()

                threads[thread_index] = threading.Thread(
                    target=process_request, args=(request,), daemon=True
                )

                threads[thread_index].start()

            # for

            # Waits for all threads.
            [thread.join() for thread in threads if thread is not None]
            print()

            # Commit changes.
            exec_cmd(
                "git commit -a -m %s" % round(time.time()),
            )

            # Reloads json.
            f = open("requests.json")
            requests = json.load(f)

            # Wait POLLING_INTERVAL
            time.sleep(float(config["REQUESTS"]["POLLING_INTERVAL"]))
        # while
    # try
    except KeyboardInterrupt:
        print()
