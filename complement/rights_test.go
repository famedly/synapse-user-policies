package complement_test

import (
	"net/http"
	"testing"

	"github.com/matrix-org/complement"
	"github.com/matrix-org/complement/client"
	"github.com/matrix-org/complement/match"
	"github.com/matrix-org/complement/must"
	"github.com/tidwall/gjson"
)

func csapi(parts ...string) []string { return append([]string{"_matrix", "client", "v3"}, parts...) }

func mustForbidden(t *testing.T, res *http.Response) {
	t.Helper()
	must.MatchResponse(t, res, match.HTTPResponse{StatusCode: http.StatusForbidden})
}

// pendingInvites counts the invites visible in the user's sync.
func pendingInvites(t *testing.T, u *client.CSAPI) int {
	t.Helper()
	res := u.MustDo(t, "GET", csapi("sync"), client.WithQueries(map[string][]string{"timeout": {"0"}}))
	return len(gjson.GetBytes(client.ParseJSON(t, res), "rooms.invite").Map())
}

// memberRoom returns a bot-created room the default user has been invited to and joined.
func memberRoom(t *testing.T, bot, user *client.CSAPI) string {
	t.Helper()
	roomID := botCreateRoom(t, bot, nil)
	bot.MustInviteRoom(t, roomID, user.UserID)
	user.MustJoinRoom(t, roomID, nil)
	return roomID
}

// adminRoom is a member room where the bot has raised the default user to power level 150 (the tombstone level),
// so Synapse itself would allow the user's request and only the module can reject it.
func adminRoom(t *testing.T, bot, user *client.CSAPI) string {
	t.Helper()
	roomID := memberRoom(t, bot, user)
	pl := bot.MustGetStateEventContent(t, roomID, "m.room.power_levels", "")
	users := pl.Get("users").Value().(map[string]any)
	users[user.UserID] = 150
	body := pl.Value().(map[string]any)
	body["users"] = users
	bot.MustDo(t, "PUT", csapi("rooms", roomID, "state", "m.room.power_levels", ""), client.WithJSONBody(t, body))
	return roomID
}

func TestRightsOfDefaultUser(t *testing.T) {
	d := complement.Deploy(t, 1)
	defer d.Destroy(t)
	bot := newBot(t, d)
	user := newDefaultUser(t, d)
	other := newDefaultUser(t, d)

	t.Run("AK-FM-POL-3.1", func(t *testing.T) {
		res := user.Do(t, "POST", csapi("createRoom"), client.WithJSONBody(t, botCreateRoomBody(
			map[string]any{"invite": []string{other.UserID}})))
		//= docs/requirements/user-policies.md#ak-fm-pol-3-1
		//= type=test
		//# THEN Synapse MUST respond with 403
		mustForbidden(t, res)
		//= docs/requirements/user-policies.md#ak-fm-pol-3-1
		//= type=test
		//# AND the invited user MUST NOT receive an invitation
		if n := pendingInvites(t, other); n != 0 {
			t.Fatalf("invitee has %d invites", n)
		}
	})

	roomID := memberRoom(t, bot, user)

	t.Run("AK-FM-POL-3.2", func(t *testing.T) {
		res := user.Do(t, "PUT", csapi("rooms", roomID, "state", "m.room.member", other.UserID),
			client.WithJSONBody(t, map[string]any{"membership": "invite"}))
		//= docs/requirements/user-policies.md#ak-fm-pol-3-2
		//= type=test
		//# THEN Synapse MUST respond with 403
		mustForbidden(t, res)
		//= docs/requirements/user-policies.md#ak-fm-pol-3-2
		//= type=test
		//# AND the other user MUST NOT receive an invitation
		if n := pendingInvites(t, other); n != 0 {
			t.Fatalf("invitee has %d invites", n)
		}
	})

	t.Run("AK-FM-POL-3.3", func(t *testing.T) {
		res := user.Do(t, "POST", csapi("rooms", roomID, "invite"),
			client.WithJSONBody(t, map[string]any{"user_id": other.UserID}))
		//= docs/requirements/user-policies.md#ak-fm-pol-3-3
		//= type=test
		//# THEN Synapse MUST respond with 403
		mustForbidden(t, res)
	})

	t.Run("AK-FM-POL-3.4", func(t *testing.T) {
		roomID := adminRoom(t, bot, user)
		before := user.MustDo(t, "GET", csapi("joined_rooms"))
		n := len(gjson.GetBytes(client.ParseJSON(t, before), "joined_rooms").Array())
		res := user.Do(t, "POST", csapi("rooms", roomID, "upgrade"),
			client.WithJSONBody(t, map[string]any{"new_version": "10"}))
		//= docs/requirements/user-policies.md#ak-fm-pol-3-4
		//= type=test
		//# THEN Synapse MUST respond with 403
		mustForbidden(t, res)
		//= docs/requirements/user-policies.md#ak-fm-pol-3-4
		//= type=test
		//# AND no new room MUST be created
		after := user.MustDo(t, "GET", csapi("joined_rooms"))
		must.MatchResponse(t, after, match.HTTPResponse{
			JSON: []match.JSON{match.JSONKeyArrayOfSize("joined_rooms", n)},
		})
	})

	t.Run("AK-FM-POL-3.5", func(t *testing.T) {
		// Synapse also rejects joins to invite-only rooms natively, and the module forbids any other join rule, so no module-only scenario exists.
		uninvited := botCreateRoom(t, bot, nil)
		res := other.Do(t, "POST", csapi("join", uninvited))
		//= docs/requirements/user-policies.md#ak-fm-pol-3-5
		//= type=test
		//# THEN Synapse MUST respond with 403
		mustForbidden(t, res)
	})

	t.Run("AK-FM-POL-3.6", func(t *testing.T) {
		roomID := adminRoom(t, bot, user)
		pl := bot.MustGetStateEventContent(t, roomID, "m.room.power_levels", "")
		changed := pl.Value().(map[string]any)
		changed["users"].(map[string]any)[other.UserID] = 50
		res := user.Do(t, "PUT", csapi("rooms", roomID, "state", "m.room.power_levels", ""),
			client.WithJSONBody(t, changed))
		//= docs/requirements/user-policies.md#ak-fm-pol-3-6
		//= type=test
		//# THEN Synapse MUST respond with 403
		mustForbidden(t, res)
		//= docs/requirements/user-policies.md#ak-fm-pol-3-6
		//= type=test
		//# AND m.room.power_levels MUST remain unchanged
		now := bot.MustGetStateEventContent(t, roomID, "m.room.power_levels", "")
		if now.Raw != pl.Raw {
			t.Fatalf("power levels changed: %s -> %s", pl.Raw, now.Raw)
		}
	})

	t.Run("AK-FM-POL-3.7", func(t *testing.T) {
		res := user.Do(t, "POST", csapi("rooms", roomID, "invite"),
			client.WithJSONBody(t, map[string]any{
				"id_server": "id.example.org", "id_access_token": "token",
				"medium": "email", "address": "x@example.org",
			}))
		//= docs/requirements/user-policies.md#ak-fm-pol-3-7
		//= type=test
		//# THEN Synapse MUST respond with 403
		must.MatchResponse(t, res, match.HTTPResponse{
			StatusCode: http.StatusForbidden,
			JSON:       []match.JSON{match.JSONKeyEqual("errcode", "M_FORBIDDEN")},
		})
	})

	t.Run("AK-FM-POL-4.1", func(t *testing.T) {
		user := newDefaultUser(t, d)
		room := botCreateRoom(t, bot, nil)
		bot.MustInviteRoom(t, room, user.UserID)
		user.MustJoinRoom(t, room, nil)
		res := user.MustDo(t, "PUT", csapi("rooms", room, "send", "m.room.message", "txn1"),
			client.WithJSONBody(t, map[string]any{"msgtype": "m.text", "body": "hallo"}))
		eventID := gjson.GetBytes(client.ParseJSON(t, res), "event_id").Str
		//= docs/requirements/user-policies.md#ak-fm-pol-4-1
		//= type=test
		//# THEN the user MUST be a member of the room
		must.MatchResponse(t, bot.MustDo(t, "GET", csapi("rooms", room, "joined_members")), match.HTTPResponse{
			JSON: []match.JSON{match.JSONKeyPresent("joined." + gjson.Escape(user.UserID))},
		})
		//= docs/requirements/user-policies.md#ak-fm-pol-4-1
		//= type=test
		//# AND the message MUST be in the room
		must.MatchResponse(t, bot.MustDo(t, "GET", csapi("rooms", room, "event", eventID)), match.HTTPResponse{
			JSON: []match.JSON{match.JSONKeyEqual("content.body", "hallo")},
		})
	})

	t.Run("AK-FM-POL-4.2", func(t *testing.T) {
		name := user.Do(t, "PUT", csapi("profile", user.UserID, "displayname"),
			client.WithJSONBody(t, map[string]any{"displayname": "Neu"}))
		avatar := user.Do(t, "PUT", csapi("profile", user.UserID, "avatar_url"),
			client.WithJSONBody(t, map[string]any{"avatar_url": "mxc://hs1/abc"}))
		//= docs/requirements/user-policies.md#ak-fm-pol-4-2
		//= type=test
		//# THEN Synapse MUST respond with 200 in each case
		must.MatchResponse(t, name, match.HTTPResponse{StatusCode: http.StatusOK})
		must.MatchResponse(t, avatar, match.HTTPResponse{StatusCode: http.StatusOK})
	})

	t.Run("AK-FM-POL-5.1", func(t *testing.T) {
		alias := "#direct:hs1"
		direct := bot.Do(t, "PUT", csapi("directory", "room", alias),
			client.WithJSONBody(t, map[string]any{"room_id": roomID}))
		viaCreate := bot.Do(t, "POST", csapi("createRoom"), client.WithJSONBody(t,
			botCreateRoomBody(map[string]any{"room_alias_name": "viacreate"})))
		//= docs/requirements/user-policies.md#ak-fm-pol-5-1
		//= type=test
		//# THEN Synapse MUST respond with 403
		mustForbidden(t, direct)
		mustForbidden(t, viaCreate)
		//= docs/requirements/user-policies.md#ak-fm-pol-5-1
		//= type=test
		//# AND the alias MUST NOT exist
		for _, a := range []string{"#direct:hs1", "#viacreate:hs1"} {
			must.MatchResponse(t, bot.Do(t, "GET", csapi("directory", "room", a)),
				match.HTTPResponse{StatusCode: http.StatusNotFound})
		}
	})
}
