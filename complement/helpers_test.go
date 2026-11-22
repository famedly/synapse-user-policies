package complement_test

// Duvet citations (//=, //= type=test, //#) go inside the test function body: gofmt
// rewrites doc comments to "// =", which duvet does not recognize.

import (
	"testing"

	"github.com/matrix-org/complement"
	"github.com/matrix-org/complement/client"
	"github.com/matrix-org/complement/helpers"
	"github.com/tidwall/gjson"
)

func newDefaultUser(t *testing.T, d complement.Deployment) *client.CSAPI {
	t.Helper()
	return d.Register(t, "hs1", helpers.RegistrationOpts{})
}

func newAdmin(t *testing.T, d complement.Deployment) *client.CSAPI {
	t.Helper()
	return d.Register(t, "hs1", helpers.RegistrationOpts{IsAdmin: true})
}

// newBot registers a user on hs1 and lets an admin set its user_type to "bot".
func newBot(t *testing.T, d complement.Deployment) *client.CSAPI {
	t.Helper()
	return newBotOn(t, d, "hs1")
}

func newBotOn(t *testing.T, d complement.Deployment, hs string) *client.CSAPI {
	t.Helper()
	bot := d.Register(t, hs, helpers.RegistrationOpts{})
	admin := d.Register(t, hs, helpers.RegistrationOpts{IsAdmin: true})
	admin.MustDo(t, "PUT", []string{"_synapse", "admin", "v2", "users", bot.UserID},
		client.WithJSONBody(t, map[string]any{"user_type": "bot"}))
	return bot
}

// botCreateRoomBody is the encrypted private room request, with extra keys merged in.
func botCreateRoomBody(extra map[string]any) map[string]any {
	body := map[string]any{
		"preset": "private_chat",
		"initial_state": []map[string]any{{
			"type":      "m.room.encryption",
			"state_key": "",
			"content":   map[string]any{"algorithm": "m.megolm.v1.aes-sha2"},
		}},
	}
	for k, v := range extra {
		body[k] = v
	}
	return body
}

// botCreateRoom creates a room as the bot and returns its room ID.
func botCreateRoom(t *testing.T, bot *client.CSAPI, extra map[string]any) string {
	t.Helper()
	res := bot.MustDo(t, "POST", []string{"_matrix", "client", "v3", "createRoom"},
		client.WithJSONBody(t, botCreateRoomBody(extra)))
	return gjson.ParseBytes(client.ParseJSON(t, res)).Get("room_id").Str
}
