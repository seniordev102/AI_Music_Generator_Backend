from enum import Enum

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db_session
from app.models import IAHCostPerAction


class CostPerActionType(str, Enum):
    ASK_IAH_QUERY = "ASK_IAH_QUERY"
    ASK_IAH_IMAGE_GENERATION = "ASK_IAH_IMAGE_GENERATION"
    ASK_IAH_PLAYLIST_GENERATION = "ASK_IAH_PLAYLIST_GENERATION"
    RFM_SONG_GENERATION = "RFM_SONG_GENERATION"
    RFM_LYRICS_GENERATION = "RFM_LYRICS_GENERATION"
    RFM_IMAGE_GENERATION = "RFM_IMAGE_GENERATION"
    RESONANCE_ART_IMAGE_GENERATION = "RES_ART_IMAGE_GENERATION"
    RESONANCE_ART_QUERY = "RESONANCE_ART_QUERY"
    SHUFFLE_AND_PLAY_PLAYLIST_GENERATION = "SHUFFLE_AND_PLAY_PLAYLIST_GENERATION"
    SHUFFLE_AND_PLAY_IMAGE_GENERATION = "SHUFFLE_AND_PLAY_IMAGE_GENERATION"
    SONIC_SUMMARY_GENERATION = "SONIC_SUMMARY_GENERATION"
    CRAFT_MY_SONG_IMAGE_GENERATION = "CRAFT_MY_SONG_IMAGE_GENERATION"
    CRAFT_MY_SONG_PLAYLIST_GENERATION = "CRAFT_MY_SONG_PLAYLIST_GENERATION"
    SONIC_INFUSIONS_IMAGE_GENERATION = "SONIC_INFUSIONS_IMAGE_GENERATION"
    SONIC_INFUSIONS_PLAYLIST_GENERATION = "SONIC_INFUSIONS_PLAYLIST_GENERATION"


class CostPerActionService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
    ):
        self.session = session

    async def seed_cost_per_action(self):
        # delete all existing cost per actions
        await self.session.execute(delete(IAHCostPerAction))
        await self.session.commit()

        # create cost per action for llm query for each key
        cost_matrix = {
            CostPerActionType.ASK_IAH_QUERY: {
                "cost": 1,
                "endpoint": "/api/v1/iah/query",
            },
            CostPerActionType.ASK_IAH_IMAGE_GENERATION: {
                "cost": 4,
                "endpoint": "/api/v1/iah/image-generation",
            },
            CostPerActionType.ASK_IAH_PLAYLIST_GENERATION: {
                "cost": 2,
                "endpoint": "/api/v1/iah/playlist-generation",
            },
            CostPerActionType.RFM_SONG_GENERATION: {
                "cost": 10,
                "endpoint": "/api/v1/craft-my-song/song-generation",
            },
            CostPerActionType.RFM_LYRICS_GENERATION: {
                "cost": 1,
                "endpoint": "/api/v1/craft-my-song/lyrics-generation",
            },
            CostPerActionType.RFM_IMAGE_GENERATION: {
                "cost": 4,
                "endpoint": "/api/v1/rfm/image-generation",
            },
            CostPerActionType.RESONANCE_ART_IMAGE_GENERATION: {
                "cost": 4,
                "endpoint": "/api/v1/resonance-art/image-generation",
            },
            CostPerActionType.RESONANCE_ART_QUERY: {
                "cost": 1,
                "endpoint": "/api/v1/resonance-art/query",
            },
            CostPerActionType.SHUFFLE_AND_PLAY_PLAYLIST_GENERATION: {
                "cost": 1,
                "endpoint": "/api/v1/shuffle-and-play/playlist-generation",
            },
            CostPerActionType.SHUFFLE_AND_PLAY_IMAGE_GENERATION: {
                "cost": 4,
                "endpoint": "/api/v1/shuffle-and-play/image-generation",
            },
            CostPerActionType.SONIC_SUMMARY_GENERATION: {
                "cost": 1,
                "endpoint": "/api/v1/sonic-summary/summary-generation",
            },
            CostPerActionType.CRAFT_MY_SONG_IMAGE_GENERATION: {
                "cost": 4,
                "endpoint": "/api/v1/craft-my-song/image-generation",
            },
            CostPerActionType.CRAFT_MY_SONG_PLAYLIST_GENERATION: {
                "cost": 1,
                "endpoint": "/api/v1/craft-my-song/playlist-generation",
            },
            CostPerActionType.SONIC_INFUSIONS_IMAGE_GENERATION: {
                "cost": 4,
                "endpoint": "/api/v1/sonic-infusions/image-generation",
            },
            CostPerActionType.SONIC_INFUSIONS_PLAYLIST_GENERATION: {
                "cost": 1,
                "endpoint": "/api/v1/sonic-infusions/playlist-generation",
            },
        }

        for action_type, data in cost_matrix.items():
            await self.create_cost_per_action(
                action_type, data["cost"], data["endpoint"]
            )

    async def create_cost_per_action(self, action_type: str, cost: int, endpoint: str):
        cost_per_action = IAHCostPerAction(
            action_type=action_type, cost=cost, endpoint=endpoint
        )
        self.session.add(cost_per_action)
        await self.session.commit()
        return cost_per_action

    async def get_cost_per_action(self, action_type: str) -> IAHCostPerAction:
        query = select(IAHCostPerAction).where(
            IAHCostPerAction.action_type == action_type
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_all_cost_per_action(self) -> list[IAHCostPerAction]:
        query = select(IAHCostPerAction)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_cost_per_action(self, action_type: str, cost: int):
        cost_per_action = await self.get_cost_per_action(action_type)
        cost_per_action.cost = cost
        await self.session.commit()
        return cost_per_action
