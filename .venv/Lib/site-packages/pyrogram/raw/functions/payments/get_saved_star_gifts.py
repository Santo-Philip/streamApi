#  Pyrofork - Telegram MTProto API Client Library for Python
#  Copyright (C) 2017-present Dan <https://github.com/delivrance>
#  Copyright (C) 2022-present Mayuri-Chan <https://github.com/Mayuri-Chan>
#
#  This file is part of Pyrofork.
#
#  Pyrofork is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Lesser General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pyrofork is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with Pyrofork.  If not, see <http://www.gnu.org/licenses/>.

from io import BytesIO

from pyrogram.raw.core.primitives import Int, Long, Int128, Int256, Bool, Bytes, String, Double, Vector
from pyrogram.raw.core import TLObject
from pyrogram import raw
from typing import List, Optional, Any

# # # # # # # # # # # # # # # # # # # # # # # #
#               !!! WARNING !!!               #
#          This is a generated file!          #
# All changes made in this file will be lost! #
# # # # # # # # # # # # # # # # # # # # # # # #


class GetSavedStarGifts(TLObject):  # type: ignore
    """Telegram API function.

    Details:
        - Layer: ``198``
        - ID: ``23830DE9``

    Parameters:
        peer (:obj:`InputPeer <pyrogram.raw.base.InputPeer>`):
            N/A

        offset (``str``):
            N/A

        limit (``int`` ``32-bit``):
            N/A

        exclude_unsaved (``bool``, *optional*):
            N/A

        exclude_saved (``bool``, *optional*):
            N/A

        exclude_unlimited (``bool``, *optional*):
            N/A

        exclude_limited (``bool``, *optional*):
            N/A

        exclude_unique (``bool``, *optional*):
            N/A

        sort_by_value (``bool``, *optional*):
            N/A

    Returns:
        :obj:`payments.SavedStarGifts <pyrogram.raw.base.payments.SavedStarGifts>`
    """

    __slots__: List[str] = ["peer", "offset", "limit", "exclude_unsaved", "exclude_saved", "exclude_unlimited", "exclude_limited", "exclude_unique", "sort_by_value"]

    ID = 0x23830de9
    QUALNAME = "functions.payments.GetSavedStarGifts"

    def __init__(self, *, peer: "raw.base.InputPeer", offset: str, limit: int, exclude_unsaved: Optional[bool] = None, exclude_saved: Optional[bool] = None, exclude_unlimited: Optional[bool] = None, exclude_limited: Optional[bool] = None, exclude_unique: Optional[bool] = None, sort_by_value: Optional[bool] = None) -> None:
        self.peer = peer  # InputPeer
        self.offset = offset  # string
        self.limit = limit  # int
        self.exclude_unsaved = exclude_unsaved  # flags.0?true
        self.exclude_saved = exclude_saved  # flags.1?true
        self.exclude_unlimited = exclude_unlimited  # flags.2?true
        self.exclude_limited = exclude_limited  # flags.3?true
        self.exclude_unique = exclude_unique  # flags.4?true
        self.sort_by_value = sort_by_value  # flags.5?true

    @staticmethod
    def read(b: BytesIO, *args: Any) -> "GetSavedStarGifts":
        
        flags = Int.read(b)
        
        exclude_unsaved = True if flags & (1 << 0) else False
        exclude_saved = True if flags & (1 << 1) else False
        exclude_unlimited = True if flags & (1 << 2) else False
        exclude_limited = True if flags & (1 << 3) else False
        exclude_unique = True if flags & (1 << 4) else False
        sort_by_value = True if flags & (1 << 5) else False
        peer = TLObject.read(b)
        
        offset = String.read(b)
        
        limit = Int.read(b)
        
        return GetSavedStarGifts(peer=peer, offset=offset, limit=limit, exclude_unsaved=exclude_unsaved, exclude_saved=exclude_saved, exclude_unlimited=exclude_unlimited, exclude_limited=exclude_limited, exclude_unique=exclude_unique, sort_by_value=sort_by_value)

    def write(self, *args) -> bytes:
        b = BytesIO()
        b.write(Int(self.ID, False))

        flags = 0
        flags |= (1 << 0) if self.exclude_unsaved else 0
        flags |= (1 << 1) if self.exclude_saved else 0
        flags |= (1 << 2) if self.exclude_unlimited else 0
        flags |= (1 << 3) if self.exclude_limited else 0
        flags |= (1 << 4) if self.exclude_unique else 0
        flags |= (1 << 5) if self.sort_by_value else 0
        b.write(Int(flags))
        
        b.write(self.peer.write())
        
        b.write(String(self.offset))
        
        b.write(Int(self.limit))
        
        return b.getvalue()
