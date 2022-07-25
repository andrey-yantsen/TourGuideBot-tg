import argparse
import logging
import sys
from . import log


def run():
    lh = logging.StreamHandler(sys.stdout)
    log.addHandler(lh)
    log.setLevel(logging.INFO)

    parser = argparse.ArgumentParser(description='TimeGueard time-switches AntiCloud')
    parser.add_argument('--debug', '-d', help='Display communication data and other debug info.',
                        action='store_true')
    args = parser.parse_args()

    if args.debug:
        log_format = '[%(asctime)s] [%(levelname)s] [%(name)s] [%(module)s:%(lineno)d] %(message)s'
        log.setLevel(logging.DEBUG)
    else:
        log_format = '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'

    lh.setFormatter(logging.Formatter(log_format, datefmt='%d/%m/%Y %H:%M:%S'))


if __name__ == '__main__':
    run()
