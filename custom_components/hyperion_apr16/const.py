"""Constants for the AudioControl Hyperion APR-16 integration."""

DOMAIN = "hyperion_apr16"
DEFAULT_PORT = 8080 # Main integration port
ATLAS_PORT = 80     # Explicit port for Connect-RPC / commands.v1.AtlasService
CONF_SESSION_COOKIE = "session_cookie"
DEFAULT_NAME = "Hyperion APR-16"

# The processor pushes its state over a WebSocket (the same one its own web UI uses).
STATE_STREAM_PORT = ATLAS_PORT
STATE_STREAM_PATH = "/ws/state"
STREAM_KINDS = ("audio", "inputs", "dirac", "speakers", "video")  # the kinds of state this integration follows

STREAM_SILENCE_TIMEOUT = 30  # seconds without a message (heartbeats included) before a connection is replaced
STREAM_CONNECT_TIMEOUT = 10
STREAM_RECONNECT_MIN = 1
STREAM_RECONNECT_MAX = 30
STREAM_STABLE_AFTER = 30

# While the streams are live the REST status is only re-read this often, as a safety net.
FULL_REFRESH_INTERVAL = 30
POLL_INTERVAL = 5

# Level meters (a streaming call on the same port as the state streams). Meter channel N is output N; the
# processor reports 20 values but only the 16 XLR outputs are used.
METER_CHANNELS = 16
METER_UPDATE_MS = 100  # how often the processor is asked for a reading; the peak-hold sees every one
METER_PUBLISH_INTERVAL = 1.0  # seconds, the shortest time between two changes shown in Home Assistant
METER_LEVEL_STEP_DB = 3  # a level is only shown again once it has moved this far
METER_AUTO_OFF = 600  # seconds the meters stay on without being switched on again
METER_SILENCE_TIMEOUT = 10  # seconds without a reading before the stream is replaced
