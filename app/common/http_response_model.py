from typing import Generic, List, Optional, TypeVar, Union

from pydantic import BaseModel
from pydantic.generics import GenericModel

DataT = TypeVar("DataT")


class PageMeta(BaseModel):
    page: int
    page_size: int
    total_pages: int
    total_items: int


class CommonResponse(GenericModel, Generic[DataT]):
    message: str
    success: bool
    payload: Optional[Union[DataT, List[DataT]]]
    meta: Optional[PageMeta]
