# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Features

- Action policies by user type: `allow` maps the actions `create_room`, `invite`, `invite_3pid`, `create_room_alias`, `publish_room`, `send_state_event` and `join_uninvited_room` to user types (fail-closed)
- Room guardrails for all users: invite-only, no `world_readable`, no guest access, encrypted with `m.megolm.v1.aes-sha2` from creation
- Member cap `max_default_members_per_room` (3PID invitations count), no federated invitations by default
- Options `always_allowed_state_events`, `alias_pattern`
- OIDC user mapping provider `RandomLocalpartMapping`: random UUIDv4 localparts, nothing taken over from the identity provider
- Erasure: media and external IDs of an account deactivated with `erase` are removed
- Complement tests, Duvet requirement coverage
