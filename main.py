#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "gui":
        from gui import main as gui_main
        gui_main()
    elif len(sys.argv) > 1:
        print(f"Module inconnu: {sys.argv[1]}")
        print("Utilisation : python main.py gui")
    else:
        from gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
