# Copyright (C) 2009 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import time


try:
    import threading as _threading
except ImportError:
    import dummy_threading as _threading

from repo_trace import IsTraceToStderr


# Capture the original stderr stream. We use this exclusively for progress
# updates to ensure we talk to the terminal even if stderr is redirected.
_STDERR = sys.stderr
_TTY = _STDERR.isatty()

# This will erase all content in the current line (wherever the cursor is).
# It does not move the cursor, so this is usually followed by \r to move to
# column 0.
CSI_ERASE_LINE = "\x1b[2K"

# This will erase all content in the current line after the cursor.  This is
# useful for partial updates & progress messages as the terminal can display
# it better.
CSI_ERASE_LINE_AFTER = "\x1b[K"


def convert_to_hms(total):
    """Converts a period of seconds to hours, minutes, and seconds."""
    hours, rem = divmod(total, 3600)
    mins, secs = divmod(rem, 60)
    return int(hours), int(mins), secs


def duration_str(total):
    """A less noisy timedelta.__str__.

    The default timedelta stringification contains a lot of leading zeros and
    uses microsecond resolution.  This makes for noisy output.
    """
    hours, mins, secs = convert_to_hms(total)
    ret = f"{secs:.3f}s"
    if mins:
        ret = f"{mins}m{ret}"
    if hours:
        ret = f"{hours}h{ret}"
    return ret


def elapsed_str(total):
    """Returns seconds in the format [H:]MM:SS.

    Does not display a leading zero for minutes if under 10 minutes. This should
    be used when displaying elapsed time in a progress indicator.
    """
    hours, mins, secs = convert_to_hms(total)
    ret = f"{int(secs):>02d}"
    if total >= 3600:
        # Show leading zeroes if over an hour.
        ret = f"{mins:>02d}:{ret}"
    else:
        ret = f"{mins}:{ret}"
    if hours:
        ret = f"{hours}:{ret}"
    return ret


def jobs_str(total):
    return f"{total} job{'s' if total > 1 else ''}"


class Progress:
    def __init__(
        self,
        title,
        total=0,
        units="",
        delay=True,
        quiet=False,
        show_elapsed=False,
        elide=False,
    ):
        self._title = title
        self._total = total
        self._done = 0
        self._start = time.time()
        self._show = not delay
        self._units = units
        self._elide = elide and _TTY
        self._quiet = quiet
        self._ended = False

        # Only show the active jobs section if we run more than one in parallel.
        self._show_jobs = False
        self._active = 0

        # Save the last message for displaying on refresh.
        self._last_msg = None
        self._show_elapsed = show_elapsed
        self._last_redis_push_time = 0
        self._last_redis_push_percent = -1
        self._update_event = _threading.Event()
        self._update_thread = _threading.Thread(
            target=self._update_loop,
        )
        self._update_thread.daemon = True

        if not quiet and show_elapsed:
            self._update_thread.start()

    def update_total(self, new_total):
        """Updates the total if the new total is larger."""
        if new_total > self._total:
            self._total = new_total

    def _update_loop(self):
        while True:
            self.update(inc=0)
            if self._update_event.wait(timeout=1):
                return

    def _write(self, s):
        s = "\r" + s
        if self._elide:
            col = os.get_terminal_size(_STDERR.fileno()).columns
            if len(s) > col:
                s = s[: col - 1] + ".."
        _STDERR.write(s)
        _STDERR.flush()

    def start(self, name):
        self._active += 1
        if not self._show_jobs:
            self._show_jobs = self._active > 1
        self.update(inc=0, msg="started " + name)

    def finish(self, name):
        self.update(msg="finished " + name)
        self._active -= 1

    def update(self, inc=1, msg=None):
        """Updates the progress indicator.

        Args:
            inc: The number of items completed.
            msg: The message to display. If None, use the last message.
        """
        if self._ended:
            return
        self._done += inc
        if msg is None:
            msg = self._last_msg
        self._last_msg = msg

        # Logic for pushing to Redis (Throttled)
        self._MaybePushToRedis()

        if not _TTY or IsTraceToStderr() or self._quiet:
            return

        elapsed_sec = time.time() - self._start
        if not self._show:
            if 0.5 <= elapsed_sec:
                self._show = True
            else:
                return

        if self._total <= 0:
            self._write("%s: %d,%s" % (self._title, self._done, CSI_ERASE_LINE_AFTER))
        else:
            p = (100 * self._done) / self._total
            if self._show_jobs:
                jobs = f"[{jobs_str(self._active)}] "
            else:
                jobs = ""
            if self._show_elapsed:
                elapsed = f" {elapsed_str(elapsed_sec)} |"
            else:
                elapsed = ""
            self._write(
                "%s: %2d%% %s(%d%s/%d%s)%s %s%s"
                % (
                    self._title,
                    p,
                    jobs,
                    self._done,
                    self._units,
                    self._total,
                    self._units,
                    elapsed,
                    msg,
                    CSI_ERASE_LINE_AFTER,
                )
            )

    def _MaybePushToRedis(self):
        """Throttled push of progress data to Redis."""
        try:
            now = time.time()
            # Calculate percentage
            p = 0
            if self._total > 0:
                p = int((100 * self._done) / self._total)
            else:
                # For indeterminate progress, we still push every 5 seconds
                p = -1

            # Throttle: every 3 seconds or every 2% change
            time_diff = now - self._last_redis_push_time
            percent_diff = abs(p - self._last_redis_push_percent)

            if time_diff > 3 or (p != -1 and percent_diff >= 2):
                self._last_redis_push_time = now
                self._last_redis_push_percent = p
                self._PushToRedis(p)
        except Exception:
            pass

    def _PushToRedis(self, p):
        """Perform the actual push to Redis."""
        try:
            import getpass
            import hashlib
            import json
            import os
            import subprocess

            username = getpass.getuser()
            workspace_path = os.getcwd()
            workspace_hash = hashlib.sha256(workspace_path.encode("utf-8")).hexdigest()[
                :12
            ]
            payload = {
                "type": "progress",
                "username": username,
                "workspace_path": workspace_path,
                "workspace_hash": workspace_hash,
                "title": self._title,
                "done": self._done,
                "total": self._total,
                "percent": p,
                "timestamp": time.time(),
            }

            payload_json = json.dumps(payload)
            # Use Popen to fire and forget - ensures we never block or stop repo sync
            cmd = ["redis-cli", "LPUSH", "global:repo_sync_notifications", payload_json]
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def display_message(self, msg):
        """Clears the current progress line and prints a message above it.

        The progress bar is then redrawn on the next line.
        """
        if not _TTY or IsTraceToStderr() or self._quiet:
            return

        # Erase the current line, print the message with a newline,
        # and then immediately redraw the progress bar on the new line.
        _STDERR.write("\r" + CSI_ERASE_LINE)
        _STDERR.write(msg + "\n")
        _STDERR.flush()
        self.update(inc=0)

    def end(self):
        if self._ended:
            return
        self._ended = True

        self._update_event.set()
        if not _TTY or IsTraceToStderr() or self._quiet:
            return

        duration = duration_str(time.time() - self._start)
        if self._total <= 0:
            self._write(
                "%s: %d, done in %s%s\n"
                % (self._title, self._done, duration, CSI_ERASE_LINE_AFTER)
            )
        else:
            p = (100 * self._done) / self._total
            self._write(
                "%s: %3d%% (%d%s/%d%s), done in %s%s\n"
                % (
                    self._title,
                    p,
                    self._done,
                    self._units,
                    self._total,
                    self._units,
                    duration,
                    CSI_ERASE_LINE_AFTER,
                )
            )
