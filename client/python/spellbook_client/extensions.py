from pydantic import validate_call, Field, StrictFloat, StrictStr, StrictInt
from typing import Any, Dict, List, Optional, Tuple, Union
from typing_extensions import Annotated

from typing import Optional
from spellbook_client.models.deck_request import DeckRequest
from spellbook_client.models.paginated_find_my_combo_response_list import PaginatedFindMyComboResponseList

from spellbook_client.api_client import ApiClient, RequestSerialized
from spellbook_client.api_response import ApiResponse
from spellbook_client.rest import RESTResponseType
from spellbook_client.api.find_my_combos_api import FindMyCombosApi


async def find_my_combos_create_plain(
    self: FindMyCombosApi,
    decklist: str,
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
) -> PaginatedFindMyComboResponseList:
    _param = self._find_my_combos_create_serialize(
        deck_request=decklist,
        _request_auth=_request_auth,
        _content_type=_content_type or 'text/plain',
        _headers=_headers,
        _host_index=_host_index
    )

    _response_types_map: Dict[str, Optional[str]] = {
        '200': "PaginatedFindMyComboResponseList",
    }
    response_data = await self.api_client.call_api(
        *_param,
        _request_timeout=_request_timeout
    )
    await response_data.read()
    return self.api_client.response_deserialize(
        response_data=response_data,
        response_types_map=_response_types_map,
    ).data
