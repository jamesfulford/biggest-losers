import os


DRY_RUN = bool(os.environ.get("DRY_RUN", ""))
if DRY_RUN:
    print('DRY RUN, will not execute any trades')
else:
    print('LIVE RUN, will execute trades')
