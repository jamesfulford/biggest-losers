import os


DRY_RUN = 'DRY_RUN' in os.environ
if DRY_RUN:
    print('DRY RUN, will not execute any trades')
else:
    print('LIVE RUN, will execute trades')
