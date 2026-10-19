# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Deprecated alias of :mod:`ovos_tts_server.utcp`."""
import warnings

from ovos_tts_server.utcp import build_utcp_manual, make_utcp_router
from ovos_tts_server.version import VERSION_MAJOR, VERSION_MINOR

__all__ = ["build_utcp_manual", "make_utcp_router"]

warnings.warn(
    "ovos_tts_server.utcp_manual is deprecated, import ovos_tts_server.utcp "
    f"instead; it will be removed in {VERSION_MAJOR}.{VERSION_MINOR + 1}.0",
    DeprecationWarning,
    stacklevel=2,
)
