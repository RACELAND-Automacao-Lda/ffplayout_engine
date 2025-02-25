# This file is part of ffplayout.
#
# ffplayout is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ffplayout is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ffplayout. If not, see <http://www.gnu.org/licenses/>.

# ------------------------------------------------------------------------------

"""
This module write the files compression directly to a hls (m3u8) playlist,
without pre- and post-processing.

Example config:

out:
    stream_output: >-
        -flags +cgop
        -f hls
        -hls_time 6
        -hls_list_size 600
        -hls_flags append_list+delete_segments+omit_endlist+program_date_time
        -hls_segment_filename /var/www/srs/live/stream-%09d.ts /var/www/srs/live/stream.m3u8

"""

import re
from importlib import import_module
from pathlib import Path
from subprocess import PIPE, Popen
from threading import Thread

from ..utils import (ff_proc, ffmpeg_stderr_reader, log, messenger, playout,
                     pre, sync_op, terminate_processes)


def clean_ts():
    """
    this function get all *.m3u8 playlists from config,
    read lines from them until it founds first *.ts file,
    then it checks if files on hard drive are older then this first *.ts
    and if so delete them
    """
    m3u8_files = [p for p in playout.stream_output if 'm3u8' in p]

    for m3u8_file in m3u8_files:
        messenger.debug(f'cleanup *.ts files from: "{m3u8_file}"')
        test_num = 0
        hls_path = Path(m3u8_file).parent

        if Path(m3u8_file).is_file():
            with open(m3u8_file, 'r') as m3u8:
                for line in m3u8:
                    if '.ts' in line:
                        test_num = int(re.findall(r'(\d+).ts', line)[0])
                        break

            for ts_file in hls_path.rglob('*.ts'):
                ts_num = int(re.findall(r'(\d+).ts', str(ts_file))[0])

                if test_num > ts_num:
                    ts_file.unlink(missing_ok=True)


def output():
    """
    this output is hls output, no pre-process is needed.
    """
    sync_op.realtime = True

    try:
        Iter = import_module(f'ffplayout.player.{pre.mode}').GetSourceIter
        get_source = Iter()

        try:
            for node in get_source.next():
                messenger.info(f'Play: {node.get("source")}')

                cmd = [
                    'ffmpeg', '-v', f'level+{log.ff_level}',
                    '-hide_banner', '-nostats'
                    ] + node['src_cmd'] + node['filter'] + playout.output_param

                messenger.debug(f'Encoder CMD: "{" ".join(cmd)}"')

                ff_proc.encoder = Popen(cmd, stdin=PIPE, stderr=PIPE)

                stderr_reader_thread = Thread(target=ffmpeg_stderr_reader,
                                              args=(ff_proc.encoder.stderr,
                                                    '[Encoder]'))
                stderr_reader_thread.daemon = True
                stderr_reader_thread.start()
                stderr_reader_thread.join()

                ts_cleaning_thread = Thread(target=clean_ts)
                ts_cleaning_thread.daemon = True
                ts_cleaning_thread.start()

        except BrokenPipeError:
            messenger.error('Broken Pipe!')
            terminate_processes(getattr(get_source, 'stop', None))

        except SystemExit:
            messenger.info('Got close command')
            terminate_processes(getattr(get_source, 'stop', None))

        except KeyboardInterrupt:
            messenger.warning('Program terminated')
            terminate_processes(getattr(get_source, 'stop', None))

        # close encoder when nothing is to do anymore
        if ff_proc.encoder.poll() is None:
            ff_proc.encoder.terminate()

    finally:
        if ff_proc.encoder.poll() is None:
            ff_proc.encoder.terminate()
        ff_proc.encoder.wait()
