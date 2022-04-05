import logging
import sys
import os

IS_DEBUG = bool(os.environ.get('DEBUG', False))
logging.basicConfig(level=logging.DEBUG if IS_DEBUG else logging.INFO,
                    format="%(asctime)-25s %(levelname)-8s %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
