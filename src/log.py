import logging
import sys

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)-25s %(levelname)-8s %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
