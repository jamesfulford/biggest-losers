from src.strat.exits.oco import place_ocos
import sys


def main():
    try:
        up, down = sys.argv[1], sys.argv[2]
    except:
        print("Usage: python3 egress.py <up> <down>")
        print("  (1.01 means 1% up, .98 means 2% down)")
        exit(1)

    up, down = float(up), float(down)
    place_ocos(up, down)
