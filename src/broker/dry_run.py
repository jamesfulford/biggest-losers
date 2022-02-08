import logging
import os


DRY_RUN = bool(os.environ.get("DRY_RUN", ""))
if DRY_RUN:
    logging.info('DRY RUN, will not execute any trades')
else:
    logging.info('LIVE RUN, will execute trades')
