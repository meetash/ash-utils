from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.datastructures import MutableHeaders


class PermissionsPolicy:
    def __init__(self, app: ASGIApp, options: dict[str, list[str]]):
        self.app = app
        self.allowed_policies = [
            "accelerometer", "ambient-light-sensor", "attribution-reporting",
            "autoplay", "bluetooth", "browsing-topics", "camera", "compute-pressure",
            "display-capture", "document-domain", "encrypted-media", "fullscreen",
            "geolocation", "gyroscope", "hid", "identity-credentials-get",
            "idle-detection", "local-fonts", "magnetometer", "microphone", "midi",
            "otp-credentials", "payment", "picture-in-picture",
            "publickey-credentials-create", "publickey-credentials-get",
            "screen-wake-lock", "serial", "storage-access", "usb", "web-share",
            "window-management", "xr-spatial-tracking"
        ]
        self.policy_header = self._generate_header_value(options)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append('Permissions-Policy', self.policy_header)
            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _generate_header_value(self, policy_dict: dict) -> str:
        policy_parts = []

        for feature, origins in policy_dict.items():
            if feature not in self.allowed_policies:
                raise ValueError(f"Invalid policy feature: {feature}")

            if not origins:
                policy_parts.append(f"{feature}=()")
                continue

            processed = []
            for origin in origins:
                origin = origin.strip().lower()
                if origin in {'self', '*', 'src'}:
                    processed.append(f"'{origin}'")
                else:
                    if not origin.startswith(("https://", "http://", "http:")):
                        raise ValueError(f"Invalid origin format: {origin}")
                    processed.append(origin)

            policy_parts.append(f"{feature}=({' '.join(processed)})")

        return ', '.join(policy_parts)
