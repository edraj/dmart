"""Path hack to allow tests to use /backend modules."""

import os
import sys

bp = os.path.dirname(os.path.realpath("."))
sys.path.append(f"{bp}/backend")
sys.path.append(f"{bp}/tests")
