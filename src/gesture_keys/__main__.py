import sys
from pathlib import Path

# Add src/ to path so imports work when running with `python -m gesture_keys`
src_dir = str(Path(__file__).resolve().parent.parent)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from gesture_keys.app import main

if __name__ == "__main__":
    main()
