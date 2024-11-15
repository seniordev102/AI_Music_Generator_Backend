from dataclasses import dataclass
from enum import Enum
from typing import Dict


class APIEndpointKey(str, Enum):
    IAH_QUERY = "iah_query"
    CRAFT_MY_SONICS = "craft_my_sonics"
    SONIC_SUPPLEMENT_SHUFFLES = "sonic_supplement_shuffles"
    SUPER_SONIC_SHUFFLES = "super_sonic_shuffles"
    IAH_PLAYLIST_GENERATION = "iah_playlist_generation"
    IAH_IMAGE_GENERATION = "iah_image_generation"
    IAH_SONG_GENERATION = "iah_song_generation"


@dataclass
class EndpointInfo:
    endpoint: str
    cost: int


class APICostManager:
    # Define mapping of keys to endpoint info
    _endpoints: Dict[APIEndpointKey, EndpointInfo] = {
        APIEndpointKey.IAH_QUERY: EndpointInfo(
            endpoint="/api/v1/oracle/ask-iah/chat-stream", cost=1
        ),
        APIEndpointKey.CRAFT_MY_SONICS: EndpointInfo(
            endpoint="/api/v1/oracle/craft-my-sonic/generate-details", cost=1
        ),
        APIEndpointKey.SONIC_SUPPLEMENT_SHUFFLES: EndpointInfo(
            endpoint="/api/v1/sonic-supplement-shuffles", cost=1
        ),
        APIEndpointKey.SUPER_SONIC_SHUFFLES: EndpointInfo(
            endpoint="/api/v1/sonic-supplement", cost=1
        ),
        APIEndpointKey.IAH_PLAYLIST_GENERATION: EndpointInfo(
            endpoint="/api/v1/iah/playlist", cost=2
        ),
        APIEndpointKey.IAH_IMAGE_GENERATION: EndpointInfo(
            endpoint="/api/v1/iah/image-generation", cost=4
        ),
        APIEndpointKey.IAH_SONG_GENERATION: EndpointInfo(
            endpoint="/api/v1/craft-my-song", cost=10
        ),
    }

    @classmethod
    def get_endpoint_info(cls, key: APIEndpointKey) -> EndpointInfo:
        """Get endpoint information by key"""
        if key not in cls._endpoints:
            raise ValueError(f"Invalid endpoint key: {key}")
        return cls._endpoints[key]

    @classmethod
    def get_endpoint(cls, key: APIEndpointKey) -> str:
        """Get endpoint URL by key"""
        return cls.get_endpoint_info(key).endpoint

    @classmethod
    def get_cost(cls, key: APIEndpointKey) -> int:
        """Get endpoint cost by key"""
        return cls.get_endpoint_info(key).cost

    @classmethod
    def get_all_endpoints(cls) -> Dict[APIEndpointKey, EndpointInfo]:
        """Get all endpoint information"""
        return cls._endpoints.copy()
