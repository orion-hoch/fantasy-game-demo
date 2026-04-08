import unittest

import lobby_store


class LobbyStoreSeatMetaTests(unittest.TestCase):
    def setUp(self):
        lobby_store._ROOMS._memory.clear()

    def _create_room_with_players(self, game_type, total_players):
        room = lobby_store.create_room(game_type, "Host", "host-token")
        room_id = room["room_id"]
        for seat_no in range(2, total_players + 1):
            lobby_store.claim_seat(room_id, f"token-{seat_no}", f"P{seat_no}", seat_no)
        return room_id

    def test_team_switch_preserves_role_if_no_conflict(self):
        room_id = self._create_room_with_players("nfl_codewords", 4)

        room = lobby_store.update_seat_meta(room_id, "host-token", {"team": "A"})
        self.assertEqual(room["seats"]["1"]["meta"], {"team": "A"})

        room = lobby_store.update_seat_meta(room_id, "host-token", {"role": "spymaster"})
        self.assertEqual(room["seats"]["1"]["meta"], {"team": "A", "role": "spymaster"})

        # Switch team — role preserved since no one else is B/spymaster
        room = lobby_store.update_seat_meta(room_id, "host-token", {"team": "B"})
        self.assertEqual(room["seats"]["1"]["meta"], {"team": "B", "role": "spymaster"})

    def test_team_switch_clears_role_on_conflict(self):
        room_id = self._create_room_with_players("nfl_codewords", 4)

        # P1 is A/spymaster, P2 is B/spymaster
        lobby_store.update_seat_meta(room_id, "host-token", {"team": "A", "role": "spymaster"})
        lobby_store.update_seat_meta(room_id, "token-2", {"team": "B", "role": "spymaster"})

        # P1 switches to team B — role cleared because B/spymaster is taken by P2
        room = lobby_store.update_seat_meta(room_id, "host-token", {"team": "B"})
        self.assertEqual(room["seats"]["1"]["meta"], {"team": "B"})

    def test_duplicate_team_role_is_rejected_immediately(self):
        room_id = self._create_room_with_players("nfl_codewords", 4)

        lobby_store.update_seat_meta(room_id, "host-token", {"team": "A", "role": "spymaster"})

        with self.assertRaisesRegex(ValueError, "Red Clue Giver is already taken"):
            lobby_store.update_seat_meta(room_id, "token-2", {"team": "A", "role": "spymaster"})

if __name__ == "__main__":
    unittest.main()
