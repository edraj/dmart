"""Path hack to allow tests to use /backend modules."""

import os
import sys

bp = os.path.dirname(os.path.realpath("."))
# print(bp)
# modpath = os.sep.join(bp + ["backend"])
# # print(modpath)
sys.path.append(f"{bp}/backend")
sys.path.append(f"{bp}/tests")
# print(sys.path)
