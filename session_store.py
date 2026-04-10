import json
import os
import urllib.error
import urllib.request


class GameStore:
    def __init__(self, namespace, ttl_seconds=14400):
        self.namespace = namespace
        self.ttl_seconds = ttl_seconds
        self._memory = {}
        self._rest_url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
        self._rest_token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
        self.backend = "vercel-kv" if self._rest_url and self._rest_token else "memory"

    def _key(self, game_id):
        return f"{self.namespace}:{game_id}"

    def _request(self, *command):
        payload = json.dumps(list(command)).encode("utf-8")
        request = urllib.request.Request(
            self._rest_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._rest_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data.get("result")

    def get(self, game_id, default=None):
        if self.backend == "memory":
            return self._memory.get(game_id, default)
        try:
            payload = self._request("GET", self._key(game_id))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return default
        if payload is None:
            return default
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return default

    def __setitem__(self, game_id, value):
        if self.backend == "memory":
            self._memory[game_id] = value
            return
        self._request("SETEX", self._key(game_id), int(self.ttl_seconds), json.dumps(value))

    def __delitem__(self, game_id):
        if self.backend == "memory":
            self._memory.pop(game_id, None)
            return
        self._request("DEL", self._key(game_id))

    def __len__(self):
        if self.backend == "memory":
            return len(self._memory)
        keys = self.keys()
        return len(keys)

    def keys(self):
        if self.backend == "memory":
            return list(self._memory.keys())
        try:
            keys = self._request("KEYS", f"{self.namespace}:*") or []
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return []
        prefix = f"{self.namespace}:"
        return [key[len(prefix):] for key in keys if key.startswith(prefix)]

    def items(self):
        if self.backend == "memory":
            return list(self._memory.items())
        result = []
        for game_id in self.keys():
            value = self.get(game_id)
            if value is not None:
                result.append((game_id, value))
        return result

    def cleanup_expired(self):
        return

    def cleanup_to_size(self, max_size):
        if self.backend != "memory":
            return
        if len(self._memory) > max_size:
            for key in list(self._memory.keys())[: max_size // 2]:
                del self._memory[key]
