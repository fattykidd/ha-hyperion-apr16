"""Constants for the AudioControl Hyperion APR-16 integration."""

DOMAIN = "hyperion_apr16"
DEFAULT_PORT = 8080 # Main integration port
ATLAS_PORT = 80     # Explicit port for Connect-RPC / commands.v1.AtlasService
CONF_SESSION_COOKIE = "session_cookie"
DEFAULT_NAME = "Hyperion APR-16"

# The processor pushes its state over a WebSocket (the same one its own web UI uses).
STATE_STREAM_PORT = ATLAS_PORT
STATE_STREAM_PATH = "/ws/state"
STREAM_KINDS = ("audio", "inputs", "dirac")  # the kinds of state this integration follows

STREAM_SILENCE_TIMEOUT = 30  # seconds without a message (heartbeats included) before a connection is replaced
STREAM_CONNECT_TIMEOUT = 10
STREAM_RECONNECT_MIN = 1
STREAM_RECONNECT_MAX = 30
STREAM_STABLE_AFTER = 30

# While the streams are live the REST status is only re-read this often, as a safety net.
FULL_REFRESH_INTERVAL = 30
POLL_INTERVAL = 5
