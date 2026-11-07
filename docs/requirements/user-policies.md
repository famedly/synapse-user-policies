# Synapse module synapse-user-policies

## Goal

### US-POL-1

Title: Only bots act, users consume

As the operator of a locked homeserver, I want only bots to create rooms and invite, so that users cannot discover or contact each other.

## Rights by user type

### FM-POL-1

Title: User type as the only source of rights

The module MUST determine a user's rights exclusively from the Synapse field user_type of their account.

An account without user_type MUST count as type default.

Note: For some actions, Synapse does not check server admins via modules, so bots have to be ordinary accounts, never server admins.

### FM-POL-2

Title: Fail-closed

An action MUST be allowed only for the user types listed for this action in the configuration allow.

If an action is missing from allow, it MUST be forbidden for all user types.

If the module cannot determine the user type of an account, it MUST reject the action.

If the module rejects an action, Synapse MUST respond with 403 and the error code M_FORBIDDEN.

### AK-FM-POL-2.1

Title: A regular user cannot create a room

GIVEN allow.create_room contains only bot

WHEN a user of type default calls createRoom

THEN Synapse MUST respond with 403 and M_FORBIDDEN

AND no room MUST be created

### AK-FM-POL-2.2

Title: A bot can create a room

GIVEN allow.create_room contains bot

WHEN a user of type bot calls createRoom with join rule invite and encryption

THEN the room MUST be created

### FM-POL-3

Title: Checked actions

The module MUST check the action create_room when a room is created and when a room is upgraded.

The module MUST check the action invite on every local invitation, including invitations in the invite field of createRoom and via the state endpoint with m.room.member.

The module MUST check the action invite_3pid on invitations by email address or phone number.

The module MUST check the action create_room_alias when an alias is created, including via room_alias_name in createRoom.

The module MUST check the action publish_room when a room is published in the room directory.

The module MUST check the action send_state_event on every PUT to a room's state endpoint.

The module MUST check the action join_uninvited_room on every join to a room the user has not been invited to.

### AK-FM-POL-3.1

Title: Invitation via createRoom is rejected

GIVEN allow.create_room and allow.invite contain only bot

WHEN a user of type default calls createRoom with an MXID in the invite field

THEN Synapse MUST respond with 403

AND the invited user MUST NOT receive an invitation

### AK-FM-POL-3.2

Title: Invitation via the state endpoint is rejected

GIVEN a user of type default is a member of a room

AND allow.invite and allow.send_state_event contain only bot

WHEN they send, via PUT to the state endpoint, an m.room.member with membership invite for another user

THEN Synapse MUST respond with 403

AND the other user MUST NOT receive an invitation

### AK-FM-POL-3.3

Title: Invitation via the invite endpoint is rejected

GIVEN a user of type default is a member of a room

WHEN they invite another user via the invite endpoint

THEN Synapse MUST respond with 403

### AK-FM-POL-3.4

Title: Room upgrade is rejected

GIVEN a user of type default is a member of a room

WHEN they request an upgrade of the room

THEN Synapse MUST respond with 403

AND no new room MUST be created

### AK-FM-POL-3.5

Title: Joining without an invitation is rejected

GIVEN a room to which a user of type default has not been invited

WHEN this user tries to join the room

THEN Synapse MUST respond with 403

### AK-FM-POL-3.6

Title: Changing power levels is rejected

GIVEN a user of type default is a member of a room

WHEN they change m.room.power_levels via the state endpoint

THEN Synapse MUST respond with 403

AND m.room.power_levels MUST remain unchanged

### AK-FM-POL-3.7

Title: Invitation by email is rejected

GIVEN a user of type default is a member of a room

WHEN they invite an email address to the room

THEN Synapse MUST respond with 403

### FM-POL-4

Title: What remains allowed

The module MUST NOT restrict login, logout, changing display name and avatar, accepting an invitation, reading and sending messages, or exchanging E2EE keys.

### AK-FM-POL-4.1

Title: A user can accept an invitation and write

GIVEN a bot has invited a user of type default into a room

WHEN the user accepts the invitation and sends a message

THEN the user MUST be a member of the room

AND the message MUST be in the room

### AK-FM-POL-4.2

Title: A user can change their profile

GIVEN a user of type default

WHEN they change their display name and their avatar

THEN Synapse MUST respond with 200 in each case

### FM-POL-5

Title: Defaults

Unless configured otherwise, allow MUST permit the actions create_room, invite, send_state_event and join_uninvited_room only for type bot.

Unless configured otherwise, allow MUST permit the actions invite_3pid, create_room_alias and publish_room for no user type.

Note: Invitations by email address or phone number are redeemed later without another module check, so they are off by default.

### AK-FM-POL-5.1

Title: Not even a bot can create an alias

GIVEN the module runs with the defaults

WHEN a user of type bot creates an alias, directly or via room_alias_name in createRoom

THEN Synapse MUST respond with 403

AND the alias MUST NOT exist

### FM-POL-6

Title: Invalid configuration

If the configuration contains an unknown action, an unknown key or a value of the wrong type, Synapse MUST NOT start.

### FM-POL-7

Title: No invitations from other homeservers

The module MUST reject every invitation from another homeserver unless allow_federated_invites is true.

Unless configured otherwise, allow_federated_invites MUST be false.

Note: Synapse gives modules no callback for a local user knocking on a room of another homeserver. Operators who need to prevent that restrict federation in Synapse itself, for example with federation_domain_whitelist.

### AK-FM-POL-7.1

Title: An invitation from another homeserver is rejected

GIVEN two homeservers that both run the module with the defaults

WHEN a user of the second homeserver invites a user of the first homeserver

THEN the invitation MUST fail

AND the invited user MUST NOT receive an invitation

## Room guardrails

### FM-POL-10

Title: Guardrails for every room

The guardrails MUST apply to users of every type, including bot.

The join rule of a room MUST always be invite.

The history visibility of a room MUST NOT be world_readable.

The guest access of a room MUST NOT be can_join.

Every room MUST be encrypted from its creation.

The encryption algorithm of a room MUST be m.megolm.v1.aes-sha2.

The module MUST reject every room creation and every event that would violate one of these conditions.

### AK-FM-POL-10.1

Title: A bot cannot create a public room

WHEN a user of type bot calls createRoom with preset public_chat

THEN Synapse MUST respond with 403

AND no room MUST be created

### AK-FM-POL-10.2

Title: A bot cannot create an unencrypted room

WHEN a user of type bot calls createRoom without m.room.encryption in initial_state

THEN Synapse MUST respond with 403

AND no room MUST be created

### AK-FM-POL-10.3

Title: A bot cannot open a room afterwards

GIVEN a room with join rule invite that a bot has created

WHEN the bot sets the join rule to public, the history visibility to world_readable or the guest access to can_join

THEN Synapse MUST reject the event

AND the room's setting MUST remain unchanged

### AK-FM-POL-10.4

Title: A bot cannot create a room with an unknown encryption algorithm

WHEN a user of type bot calls createRoom with m.room.encryption in initial_state whose algorithm is not m.megolm.v1.aes-sha2

THEN Synapse MUST respond with 403

AND no room MUST be created

### AK-FM-POL-10.5

Title: A bot cannot change the encryption algorithm

GIVEN an encrypted room that a bot has created

WHEN the bot sends m.room.encryption with empty content or with algorithm none

THEN Synapse MUST reject the event

AND the room's encryption algorithm MUST remain m.megolm.v1.aes-sha2

### FM-POL-11

Title: At most one non-bot user per room

The module MUST ensure that in a room at most as many users who are not of type bot have ever been invited or been members as max_default_members_per_room specifies.

Unless configured otherwise, max_default_members_per_room MUST equal 1.

Multiple users of type bot MUST be allowed in a room.

The limit MUST also apply to invitations by email address or phone number, whose invitee counts as a user who is not of type bot.

Every m.room.third_party_invite in the room MUST count as one user who is not of type bot, also after it has been redeemed.

Note: All users not of type bot count, including those who left the room or were banned.

Note: The module checks the limit inside one Synapse process. With several workers, two invitations processed at the same time on different workers can both pass, so deployments with workers route all membership requests of a room to one worker.

### AK-FM-POL-11.1

Title: A second non-bot user in the room is rejected

GIVEN a room in which a user of type default is already invited or a member

WHEN a bot invites a second user of type default

THEN Synapse MUST respond with 403

AND the second user MUST NOT receive an invitation

### AK-FM-POL-11.2

Title: A second bot in the room is allowed

GIVEN a room with a bot and a user of type default

WHEN the bot invites a second bot

THEN the second bot MUST receive the invitation

### AK-FM-POL-11.3

Title: The room of a non-bot user who left stays closed

GIVEN a room that a user of type default has left

WHEN a bot invites another user of type default

THEN Synapse MUST respond with 403

AND the other user MUST NOT receive an invitation

### AK-FM-POL-11.4

Title: An invitation by email counts towards the limit

GIVEN allow.invite_3pid contains bot

AND a room in which a user of type default is already invited or a member

WHEN a bot invites an email address to the room

THEN Synapse MUST respond with 403 and M_FORBIDDEN

## Accounts from single sign-on

### FM-POL-30

Title: Random localparts for accounts from single sign-on

The module MUST provide the OIDC user mapping provider synapse_user_policies.RandomLocalpartMapping.

The mapping provider MUST use the claim sub of the identity provider as the remote user ID.

For a new account, the mapping provider MUST return a localpart that is the lower-case text form of a random UUIDv4.

The mapping provider MUST NOT let the user confirm or choose the localpart.

For a new account, the mapping provider MUST take over the claim name of the identity provider as the display name, if it is present.

The mapping provider MUST NOT take over an avatar or email addresses from the identity provider.

When an account is created whose display name equals its localpart, the module MUST remove the display name.

Note: Synapse finds an existing account by identity provider and remote user ID and calls the mapping provider only for new accounts. A localpart from an email address or a name could be guessed. Synapse gives a new account its localpart as display name when the provider has no name (Apple); the module removes it, so clients and the operator see that no name is set. The name is taken over at the first sign-in only; Synapse does not update them later unless its sso.update_profile_information is on.

### FM-POL-31

Title: No media and no external IDs after erasure

When an account of the homeserver is deactivated with erase, the module MUST delete all media the account uploaded.

When an account of the homeserver is deactivated with erase, the module MUST remove the account's external IDs.

This MUST apply to deactivation by a server admin and by the user.

Note: Synapse itself deletes neither media nor external IDs on deactivation. Without the external IDs the erased account is no longer linked to the person's account at the identity provider, and a new sign-in with it creates a new account instead of ending on the erased one. The module API has no calls for either, so the module uses Synapse's store and media repository, as Synapse's admin API does.

## Delivery

### FM-POL-20

Title: No dependencies of its own

At runtime, the module MUST NOT need Python packages other than Synapse and the standard library.

Note: This way it can be delivered as plain files, for example via a ConfigMap.
