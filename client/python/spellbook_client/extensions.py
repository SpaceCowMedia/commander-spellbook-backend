from pydantic import Field, StrictFloat, StrictStr, StrictInt
from typing import Any, Dict, Optional, Tuple, Union
from typing_extensions import Annotated
from spellbook_client import PaginatedFindMyCombosResponseList
from spellbook_client.api.find_my_combos_api import FindMyCombosApi


async def find_my_combos_create_plain(
    self: FindMyCombosApi,
    decklist: str,
    limit: Optional[StrictInt] = None,
    offset: Optional[StrictInt] = None,
    _request_timeout: Union[
        None,
        Annotated[StrictFloat, Field(gt=0)],
        Tuple[
            Annotated[StrictFloat, Field(gt=0)],
            Annotated[StrictFloat, Field(gt=0)]
        ]
    ] = None,
    _request_auth: Optional[Dict[StrictStr, Any]] = None,
    _content_type: Optional[StrictStr] = None,
    _headers: Optional[Dict[StrictStr, Any]] = None,
    _host_index: Annotated[StrictInt, Field(ge=0, le=0)] = 0,
) -> PaginatedFindMyCombosResponseList:
    _param = self._find_my_combos_create_serialize(
        deck_request=decklist,
        limit=limit,
        offset=offset,
        _request_auth=_request_auth,
        _content_type=_content_type or 'text/plain',
        _headers=_headers,
        _host_index=_host_index
    )

    _response_types_map: Dict[str, Optional[str]] = {
        '200': "PaginatedFindMyCombosResponseList",
    }
    response_data = await self.api_client.call_api(
        *_param,
        _request_timeout=_request_timeout
    )
    await response_data.read()
    return self.api_client.response_deserialize(
        response_data=response_data,
        response_types_map=_response_types_map,
    ).data  # type: ignore
