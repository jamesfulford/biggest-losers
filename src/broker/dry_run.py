import logging
import os


DRY_RUN = bool(os.environ.get("DRY_RUN", ""))
if DRY_RUN:
    logging.info('DRY_RUN, will not execute any trades')
else:
    logging.info('LIVE RUN, will execute trades')
