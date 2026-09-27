"""Launch the M1 console build: `python scripts/run_console.py`.

Run with the `local-voice` conda environment active
(`conda activate local-voice`), from anywhere in the repo.
"""

import multiprocessing as mp
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from local_voice.main import main  # noqa: E402

if __name__ == "__main__":
    mp.freeze_support()
    main()
