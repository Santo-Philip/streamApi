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


class StarGiftUnique(TLObject):  # type: ignore
    """Telegram API type.

    Constructor of :obj:`~pyrogram.raw.base.StarGift`.

    Details:
        - Layer: ``198``
        - ID: ``F2FE7E4A``

    Parameters:
        id (``int`` ``64-bit``):
            N/A

        title (``str``):
            N/A

        slug (``str``):
            N/A

        num (``int`` ``32-bit``):
            N/A

        attributes (List of :obj:`StarGiftAttribute <pyrogram.raw.base.StarGiftAttribute>`):
            N/A

        availability_issued (``int`` ``32-bit``):
            N/A

        availability_total (``int`` ``32-bit``):
            N/A

        owner_id (:obj:`Peer <pyrogram.raw.base.Peer>`, *optional*):
            N/A

        owner_name (``str``, *optional*):
            N/A

        owner_address (``str``, *optional*):
            N/A

    """

    __slots__: List[str] = ["id", "title", "slug", "num", "attributes", "availability_issued", "availability_total", "owner_id", "owner_name", "owner_address"]

    ID = 0xf2fe7e4a
    QUALNAME = "types.StarGiftUnique"

    def __init__(self, *, id: int, title: str, slug: str, num: int, attributes: List["raw.base.StarGiftAttribute"], availability_issued: int, availability_total: int, owner_id: "raw.base.Peer" = None, owner_name: Optional[str] = None, owner_address: Optional[str] = None) -> None:
        self.id = id  # long
        self.title = title  # string
        self.slug = slug  # string
        self.num = num  # int
        self.attributes = attributes  # Vector<StarGiftAttribute>
        self.availability_issued = availability_issued  # int
        self.availability_total = availability_total  # int
        self.owner_id = owner_id  # flags.0?Peer
        self.owner_name = owner_name  # flags.1?string
        self.owner_address = owner_address  # flags.2?string

    @staticmethod
    def read(b: BytesIO, *args: Any) -> "StarGiftUnique":
        
        flags = Int.read(b)
        
        id = Long.read(b)
        
        title = String.read(b)
        
        slug = String.read(b)
        
        num = Int.read(b)
        
        owner_id = TLObject.read(b) if flags & (1 << 0) else None
        
        owner_name = String.read(b) if flags & (1 << 1) else None
        owner_address = String.read(b) if flags & (1 << 2) else None
        attributes = TLObject.read(b)
        
        availability_issued = Int.read(b)
        
        availability_total = Int.read(b)
        
        return StarGiftUnique(id=id, title=title, slug=slug, num=num, attributes=attributes, availability_issued=availability_issued, availability_total=availability_total, owner_id=owner_id, owner_name=owner_name, owner_address=owner_address)

    def write(self, *args) -> bytes:
        b = BytesIO()
        b.write(Int(self.ID, False))

        flags = 0
        flags |= (1 << 0) if self.owner_id is not None else 0
        flags |= (1 << 1) if self.owner_name is not None else 0
        flags |= (1 << 2) if self.owner_address is not None else 0
        b.write(Int(flags))
        
        b.write(Long(self.id))
        
        b.write(String(self.title))
        
        b.write(String(self.slug))
        
        b.write(Int(self.num))
        
        if self.owner_id is not None:
            b.write(self.owner_id.write())
        
        if self.owner_name is not None:
            b.write(String(self.owner_name))
        
        if self.owner_address is not None:
            b.write(String(self.owner_address))
        
        b.write(Vector(self.attributes))
        
        b.write(Int(self.availability_issued))
        
        b.write(Int(self.availability_total))
        
        return b.getvalue()
