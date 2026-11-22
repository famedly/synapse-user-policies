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

func TestBotGuardrails(t *testing.T) {
	d := complement.Deploy(t, 1)
	defer d.Destroy(t)
	bot := newBot(t, d)

	joinedCount := func() int {
		res := bot.MustDo(t, "GET", csapi("joined_rooms"))
		return len(gjson.GetBytes(client.ParseJSON(t, res), "joined_rooms").Array())
	}

	t.Run("AK-FM-POL-10.1", func(t *testing.T) {
		n := joinedCount()
		res := bot.Do(t, "POST", csapi("createRoom"), client.WithJSONBody(t,
			botCreateRoomBody(map[string]any{"preset": "public_chat"})))
		//= docs/requirements/user-policies.md#ak-fm-pol-10-1
		//= type=test
		//# THEN Synapse MUST respond with 403
		mustForbidden(t, res)
		//= docs/requirements/user-policies.md#ak-fm-pol-10-1
		//= type=test
		//# AND no room MUST be created
		if got := joinedCount(); got != n {
			t.Fatalf("joined rooms %d -> %d", n, got)
		}
	})

	t.Run("AK-FM-POL-10.2", func(t *testing.T) {
		n := joinedCount()
		res := bot.Do(t, "POST", csapi("createRoom"), client.WithJSONBody(t,
			map[string]any{"preset": "private_chat"}))
		//= docs/requirements/user-policies.md#ak-fm-pol-10-2
		//= type=test
		//# THEN Synapse MUST respond with 403
		mustForbidden(t, res)
		//= docs/requirements/user-policies.md#ak-fm-pol-10-2
		//= type=test
		//# AND no room MUST be created
		if got := joinedCount(); got != n {
			t.Fatalf("joined rooms %d -> %d", n, got)
		}
	})

	t.Run("AK-FM-POL-10.3", func(t *testing.T) {
		roomID := botCreateRoom(t, bot, nil)
		for _, c := range []struct{ typ, key, bad, old string }{
			{"m.room.join_rules", "join_rule", "public", "invite"},
			{"m.room.history_visibility", "history_visibility", "world_readable", "shared"},
			{"m.room.guest_access", "guest_access", "can_join", "forbidden"},
		} {
			res := bot.Do(t, "PUT", csapi("rooms", roomID, "state", c.typ, ""),
				client.WithJSONBody(t, map[string]any{c.key: c.bad}))
			//= docs/requirements/user-policies.md#ak-fm-pol-10-3
			//= type=test
			//# THEN Synapse MUST reject the event
			if res.StatusCode < 400 {
				t.Fatalf("%s=%s accepted with %d", c.typ, c.bad, res.StatusCode)
			}
			//= docs/requirements/user-policies.md#ak-fm-pol-10-3
			//= type=test
			//# AND the room's setting MUST remain unchanged
			must.MatchResponse(t, bot.Do(t, "GET", csapi("rooms", roomID, "state", c.typ, "")), match.HTTPResponse{
				JSON: []match.JSON{match.JSONKeyEqual(c.key, c.old)},
			})
		}
	})
}

func TestEncryptionAlgorithm(t *testing.T) {
	d := complement.Deploy(t, 1)
	defer d.Destroy(t)
	bot := newBot(t, d)

	t.Run("AK-FM-POL-10.4", func(t *testing.T) {
		before := len(gjson.GetBytes(client.ParseJSON(t, bot.MustDo(t, "GET", csapi("joined_rooms"))), "joined_rooms").Array())
		body := botCreateRoomBody(map[string]any{"initial_state": []map[string]any{{
			"type": "m.room.encryption", "state_key": "", "content": map[string]any{"algorithm": "none"},
		}}})
		res := bot.Do(t, "POST", csapi("createRoom"), client.WithJSONBody(t, body))
		//= docs/requirements/user-policies.md#ak-fm-pol-10-4
		//= type=test
		//# THEN Synapse MUST respond with 403
		mustForbidden(t, res)
		//= docs/requirements/user-policies.md#ak-fm-pol-10-4
		//= type=test
		//# AND no room MUST be created
		after := len(gjson.GetBytes(client.ParseJSON(t, bot.MustDo(t, "GET", csapi("joined_rooms"))), "joined_rooms").Array())
		if after != before {
			t.Fatalf("joined rooms %d -> %d", before, after)
		}
	})

	t.Run("AK-FM-POL-10.5", func(t *testing.T) {
		roomID := botCreateRoom(t, bot, nil)
		for _, content := range []map[string]any{{}, {"algorithm": "none"}} {
			res := bot.Do(t, "PUT", csapi("rooms", roomID, "state", "m.room.encryption", ""),
				client.WithJSONBody(t, content))
			//= docs/requirements/user-policies.md#ak-fm-pol-10-5
			//= type=test
			//# THEN Synapse MUST reject the event
			if res.StatusCode < 400 {
				t.Fatalf("m.room.encryption %v accepted with %d", content, res.StatusCode)
			}
			//= docs/requirements/user-policies.md#ak-fm-pol-10-5
			//= type=test
			//# AND the room's encryption algorithm MUST remain m.megolm.v1.aes-sha2
			must.MatchResponse(t, bot.Do(t, "GET", csapi("rooms", roomID, "state", "m.room.encryption", "")), match.HTTPResponse{
				JSON: []match.JSON{match.JSONKeyEqual("algorithm", "m.megolm.v1.aes-sha2")},
			})
		}
	})
}

func TestAdminBypassIsDocumented(t *testing.T) {
	d := complement.Deploy(t, 1)
	defer d.Destroy(t)
	admin := newAdmin(t, d)
	res := admin.Do(t, "POST", csapi("createRoom"), client.WithJSONBody(t, botCreateRoomBody(nil)))
	must.MatchResponse(t, res, match.HTTPResponse{StatusCode: http.StatusOK})
}
