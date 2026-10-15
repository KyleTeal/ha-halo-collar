"""Constants for the Halo Android login and read API.

The Android application id, version, user agent, and client credential are the
same public app constants the Halo Android app sends. They are not a user's
password. The unofficial client documents them:

https://github.com/sevenlayercookie/halo-collar-api
"""

from __future__ import annotations

API_BASE_URL = "https://api.halocollar.com"
AUTH_BASE_URL = "https://auth.halocollar.com"
TOKEN_PATH = "/connect/token"

ANDROID_CLIENT_ID = "halo.app.android"
# versionName.versionCode from the current Play Store build of com.paws.haloapp.
# Halo returns HTTP 400 errorCode 3003 when this falls behind the app.
ANDROID_APP_VERSION = "2.16.0.606"
ANDROID_TOKEN_USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 13)"
ANDROID_CLIENT_SECRET = "34fcPOX6rChDi83@"
SCOPE = "openid email offline_access api.dogpark"

UNKNOWN_PARALLEL_CALL_VERSION = "0"
TOKEN_EXPIRY_SLACK_SECONDS = 60
