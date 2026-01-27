from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Receive, Scope, Send


class PermissionsPolicy:
    def __init__(self, app: ASGIApp, Option: dict[str, list[str]]) -> None:  # noqa: N803
        self.app = app
        self.allowed_policies = [
            "accelerometer",
            "ambient-light-sensor",
            "attribution-reporting",
            "autoplay",
            "bluetooth",
            "browsing-topics",
            "camera",
            "compute-pressure",
            "display-capture",
            "document-domain",
            "encrypted-media",
            "fullscreen",
            "geolocation",
            "gyroscope",
            "hid",
            "identity-credentials-get",
            "idle-detection",
            "local-fonts",
            "magnetometer",
            "microphone",
            "midi",
            "otp-credentials",
            "payment",
            "picture-in-picture",
            "publickey-credentials-create",
            "publickey-credentials-get",
            "screen-wake-lock",
            "serial",
            "storage-access",
            "usb",
            "web-share",
            "window-management",
            "xr-spatial-tracking",
        ]
        self.policy_header = self._generate_header_value(Option)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # pragma: no cover
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append("Permissions-Policy", self.policy_header)
            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _generate_header_value(self, policy_dict: dict) -> str:
        policy_parts = []

        for feature, origins in policy_dict.items():
            if feature not in self.allowed_policies:
                msg = f"Invalid policy feature: {feature}"
                raise ValueError(msg)

            if not origins:
                policy_parts.append(f"{feature}=()")
                continue

            processed = []
            for origin in origins:
                origin_lower = origin.strip().lower()
                if origin_lower in {"self", "*", "src"}:
                    processed.append(f"'{origin_lower}'")
                else:
                    if not origin.startswith(("https://", "http://", "http:")):
                        msg = f"Invalid origin format: {origin_lower}"
                        raise ValueError(msg)
                    processed.append(origin_lower)

            policy_parts.append(f"{feature}=({' '.join(processed)})")

        return ", ".join(policy_parts)
