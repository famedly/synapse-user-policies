from typing import Literal

from synapse.module_api import NOT_SPAM, ModuleApi
from synapse.module_api.errors import Codes, SynapseError
from synapse.types import JsonDict, RoomAlias

from synapse_user_policies import config as cfg
from synapse_user_policies.guardrails import check_create_room, state_event_violation


class UserPolicies:
    parse_config = staticmethod(cfg.parse_config)

    def __init__(self, config: cfg.Config, api: ModuleApi):
        self._config = config
        self._api = api
        ##= docs/requirements/user-policies.md#fm-pol-4
        ## The module MUST NOT restrict login, logout, changing display name and avatar, accepting an invitation, reading and sending messages, or exchanging E2EE keys.
        # Deliberately not registered: check_username_for_spam, check_registration_for_spam,
        # check_event_for_spam, user_may_join_room for invited users (returns NOT_SPAM below),
        # and every login, profile, message and key callback.
        api.register_spam_checker_callbacks(
            user_may_create_room=self.user_may_create_room,
            user_may_invite=self.user_may_invite,
            federated_user_may_invite=self.federated_user_may_invite,
            user_may_send_3pid_invite=self.user_may_send_3pid_invite,
            user_may_create_room_alias=self.user_may_create_room_alias,
            user_may_publish_room=self.user_may_publish_room,
            user_may_send_state_event=self.user_may_send_state_event,
            user_may_join_room=self.user_may_join_room,
        )
        api.register_third_party_rules_callbacks(
            check_event_allowed=self.check_event_allowed,
            on_create_room=self.on_create_room,
            on_user_deactivation_status_changed=self.on_user_deactivation_status_changed,
        )

    ##= docs/requirements/user-policies.md#fm-pol-10
    ## The guardrails MUST apply to users of every type, including bot.
    async def on_create_room(
        self, requester, request_content: JsonDict, is_requester_admin: bool
    ) -> None:
        # No user-type or admin check on purpose: guardrails apply to everyone.
        reason = check_create_room(request_content)
        if reason:
            raise SynapseError(403, reason, Codes.FORBIDDEN)

    async def check_event_allowed(self, event, state_events):
        if (
            event.is_state()
            and event.state_key == ""
            and state_event_violation(event.type, event.content)
        ):
            return False, None
        return True, None

    ##= docs/requirements/user-policies.md#fm-pol-1
    ## The module MUST determine a user's rights exclusively from the Synapse field user_type of their account.
    ##= docs/requirements/user-policies.md#fm-pol-1
    ## An account without user_type MUST count as type default.
    async def _user_type(self, user_id: str) -> tuple[bool, str | None]:
        info = await self._api.get_userinfo_by_id(user_id)
        if info is None:
            return False, None
        return True, info.user_type

    ##= docs/requirements/user-policies.md#fm-pol-2
    ## If the module cannot determine the user type of an account, it MUST reject the action.
    ##= docs/requirements/user-policies.md#fm-pol-2
    ## If the module rejects an action, Synapse MUST respond with 403 and the error code M_FORBIDDEN.
    async def _gate(self, action: str, user_id: str) -> Literal["NOT_SPAM"] | Codes:
        found, user_type = await self._user_type(user_id)
        # Codes.FORBIDDEN is M_FORBIDDEN, which Synapse answers with 403.
        if found and cfg.allowed(self._config, action, user_type):
            return NOT_SPAM
        return Codes.FORBIDDEN

    ##= docs/requirements/user-policies.md#fm-pol-3
    ## The module MUST check the action create_room when a room is created and when a room is upgraded.
    async def user_may_create_room(self, user_id: str, room_config: JsonDict):
        return await self._gate("create_room", user_id)

    ##= docs/requirements/user-policies.md#fm-pol-3
    ## The module MUST check the action invite on every local invitation, including invitations in the invite field of createRoom and via the state endpoint with m.room.member.
    async def user_may_invite(self, inviter: str, invitee: str, room_id: str):
        verdict = await self._gate("invite", inviter)
        if verdict is not NOT_SPAM:
            return verdict
        ##= docs/requirements/user-policies.md#fm-pol-11
        ## Multiple users of type bot MUST be allowed in a room.
        # Unknown invitee counts as non-bot (fail-closed).
        _, invitee_type = await self._user_type(invitee)
        if invitee_type != "bot" and await self._default_member_count(
            room_id, exclude=invitee
        ) >= (self._config.max_default_members_per_room):
            return Codes.FORBIDDEN
        return NOT_SPAM

    ##= docs/requirements/user-policies.md#fm-pol-11
    ## The module MUST ensure that in a room at most as many users who are not of type bot have ever been invited or been members as max_default_members_per_room specifies.
    ##= docs/requirements/user-policies.md#fm-pol-11
    ## Unless configured otherwise, max_default_members_per_room MUST equal 1.
    ##= docs/requirements/user-policies.md#fm-pol-11
    ## Every m.room.third_party_invite in the room MUST count as one user who is not of type bot, also after it has been redeemed.
    async def _default_member_count(
        self, room_id: str, exclude: str | None = None
    ) -> int:
        # Counts every non-bot member entry of any membership (left and banned too).
        # exclude: the invitee, so re-inviting an existing member does not count them twice.
        state = await self._api.get_room_state(
            room_id, [("m.room.member", None), ("m.room.third_party_invite", None)]
        )
        count = 0
        for event_type, state_key in state:
            if event_type == "m.room.third_party_invite":
                # The invitee is unknown until redeemed: count as non-bot (fail-closed).
                count += 1
                continue
            if state_key == exclude:
                continue
            _, user_type = await self._user_type(state_key)
            count += user_type != "bot"  # unknown userinfo also yields None
        return count

    ##= docs/requirements/user-policies.md#fm-pol-3
    ## The module MUST check the action invite_3pid on invitations by email address or phone number.
    ##= docs/requirements/user-policies.md#fm-pol-11
    ## The limit MUST also apply to invitations by email address or phone number, whose invitee counts as a user who is not of type bot.
    async def user_may_send_3pid_invite(
        self, inviter: str, medium: str, address: str, room_id: str
    ):
        verdict = await self._gate("invite_3pid", inviter)
        # Synapse does not call user_may_invite when the invitation is redeemed, so the cap is checked here.
        if verdict is NOT_SPAM and await self._default_member_count(room_id) >= (
            self._config.max_default_members_per_room
        ):
            return Codes.FORBIDDEN
        return verdict

    ##= docs/requirements/user-policies.md#fm-pol-7
    ## The module MUST reject every invitation from another homeserver unless allow_federated_invites is true.
    async def federated_user_may_invite(self, event):
        if self._config.allow_federated_invites:
            return NOT_SPAM
        return Codes.FORBIDDEN

    ##= docs/requirements/user-policies.md#fm-pol-3
    ## The module MUST check the action create_room_alias when an alias is created, including via room_alias_name in createRoom.
    async def user_may_create_room_alias(self, user_id: str, room_alias: RoomAlias):
        verdict = await self._gate("create_room_alias", user_id)
        pattern = self._config.alias_pattern
        # Prefix match: patterns like ^#[a-z0-9]{24}: describe only the start of the alias.
        if (
            verdict is NOT_SPAM
            and pattern
            and not pattern.match(room_alias.to_string())
        ):
            return Codes.FORBIDDEN
        return verdict

    ##= docs/requirements/user-policies.md#fm-pol-3
    ## The module MUST check the action publish_room when a room is published in the room directory.
    async def user_may_publish_room(self, user_id: str, room_id: str):
        return await self._gate("publish_room", user_id)

    ##= docs/requirements/user-policies.md#fm-pol-3
    ## The module MUST check the action send_state_event on every PUT to a room's state endpoint.
    async def user_may_send_state_event(
        self,
        user_id: str,
        room_id: str,
        event_type: str,
        state_key: str,
        content: JsonDict,
    ):
        if event_type in self._config.always_allowed_state_events:
            return NOT_SPAM
        return await self._gate("send_state_event", user_id)

    ##= docs/requirements/user-policies.md#fm-pol-3
    ## The module MUST check the action join_uninvited_room on every join to a room the user has not been invited to.
    async def user_may_join_room(self, user_id: str, room_id: str, is_invited: bool):
        if is_invited:
            return NOT_SPAM
        return await self._gate("join_uninvited_room", user_id)

    ##= docs/requirements/user-policies.md#fm-pol-31
    ## When an account of the homeserver is deactivated with erase, the module MUST delete all media the account uploaded.
    ##= docs/requirements/user-policies.md#fm-pol-31
    ## When an account of the homeserver is deactivated with erase, the module MUST remove the account's external IDs.
    ##= docs/requirements/user-policies.md#fm-pol-31
    ## This MUST apply to deactivation by a server admin and by the user.
    async def on_user_deactivation_status_changed(
        self, user_id: str, deactivated: bool, by_admin: bool
    ) -> None:
        # The module API has neither media nor external ID calls: this uses Synapse's store and
        # media repository, as its admin API does (DELETE /_synapse/admin/v1/users/<id>/media,
        # PUT /_synapse/admin/v2/users/<id> with external_ids). Synapse marks the user erased
        # before it calls this.
        hs = self._api._hs
        store = hs.get_datastores().main
        if not deactivated or not await store.is_user_erased(user_id):
            return
        for auth_provider, external_id in await store.get_external_ids_by_user(user_id):
            await store.remove_user_external_id(auth_provider, external_id, user_id)
        media_ids: list[str] = []
        while True:
            page, total = await store.get_local_media_by_user_paginate(
                len(media_ids), 100, user_id
            )
            media_ids += [m.media_id for m in page]
            if not page or len(media_ids) >= total:
                break
        if media_ids:
            await hs.get_media_repository().delete_local_media_ids(media_ids)
