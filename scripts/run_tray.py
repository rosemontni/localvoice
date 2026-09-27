"""Launch the system-tray build: `pythonw scripts/run_tray.py` (no console
window) or `python scripts/run_tray.py` (for debugging, logs also print).

Run with the `local-voice` conda environment active, or via the installed
app's own environment (see installer/).
"""

import multiprocessing as mp
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from local_voice.tray_app import main  # noqa: E402

if __name__ == "__main__":
    mp.freeze_support()
    main()
