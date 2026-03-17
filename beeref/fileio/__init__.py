# This file is part of BeeRef.
#
# BeeRef is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BeeRef is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BeeRef.  If not, see <https://www.gnu.org/licenses/>.

from beeref.fileio.errors import BeeFileIOError
from beeref.fileio.io import drain_bee, load_bee, load_images, save_bee
from beeref.fileio.scratch import (
    create_scratch_file,
    delete_scratch_file,
    derive_swp_path,
    list_recovery_files,
)
from beeref.types.snapshot import IOResult, LoadResult, SaveResult
from beeref.fileio.sql import is_bee_file
from beeref.fileio.thread import ThreadedIO

__all__ = [
    "BeeFileIOError",
    "IOResult",
    "LoadResult",
    "SaveResult",
    "ThreadedIO",
    "create_scratch_file",
    "delete_scratch_file",
    "derive_swp_path",
    "drain_bee",
    "is_bee_file",
    "list_recovery_files",
    "load_bee",
    "load_images",
    "save_bee",
]
