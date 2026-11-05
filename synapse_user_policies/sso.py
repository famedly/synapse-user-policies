"""Accounts created by Synapse's own SSO (`oidc_providers`): random localparts, nothing taken
over from the identity provider."""

import uuid
from typing import Any


##= docs/requirements/user-policies.md#fm-pol-30
## The module MUST provide the OIDC user mapping provider synapse_user_policies.RandomLocalpartMapping.
class RandomLocalpartMapping:
    def __init__(self, config: Any, module_api: Any = None):
        # Synapse passes the ModuleApi only to providers that accept it; neither is needed.
        pass

    @staticmethod
    def parse_config(config: dict) -> None:
        if config:
            raise ValueError("RandomLocalpartMapping takes no configuration")

    ##= docs/requirements/user-policies.md#fm-pol-30
    ## The mapping provider MUST use the claim sub of the identity provider as the remote user ID.
    def get_remote_user_id(self, userinfo: Any) -> str:
        return str(userinfo["sub"])

    async def map_user_attributes(
        self, userinfo: Any, token: Any, failures: int
    ) -> dict:
        # Only called for a new account: Synapse finds known users by (idp_id, sub).
        ##= docs/requirements/user-policies.md#fm-pol-30
        ## For a new account, the mapping provider MUST return a localpart that is the lower-case text form of a random UUIDv4.
        ##= docs/requirements/user-policies.md#fm-pol-30
        ## The mapping provider MUST NOT let the user confirm or choose the localpart.
        ##= docs/requirements/user-policies.md#fm-pol-30
        ## The mapping provider MUST NOT take over a display name, an avatar or email addresses from the identity provider.
        return {
            "localpart": str(uuid.uuid4()),
            "confirm_localpart": False,
            "display_name": None,
            "picture": None,
            "emails": [],
        }

    async def get_extra_attributes(self, userinfo: Any, token: Any) -> dict:
        return {}
