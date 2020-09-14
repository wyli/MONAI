# Copyright 2020 MONAI Consortium
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This file should run with the minimal system requirements

import sys

PY_REQUIRED_MAJOR = 3
PY_REQUIRED_MINOR = 6


def py_version_ok(file=sys.stderr):
    if not (sys.version_info.major == PY_REQUIRED_MAJOR and sys.version_info.minor >= PY_REQUIRED_MINOR):
        print(
            "MONAI requires Python {}.{} or higher. But the current Python is: ".format(
                PY_REQUIRED_MAJOR, PY_REQUIRED_MINOR
            ),
            file=file,
            flush=True,
        )
        print(sys.version, file=file, flush=True)
        return False
    return True


if __name__ == "__main__":
    sys.exit(int(not py_version_ok()))
