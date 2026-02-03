# openwisp_controller/config/converters.py
import uuid


class UUIDAnyConverter:
    # dashed OR no-dash UUID
    regex = (
        r"(?:"
        r"[0-9a-fA-F]{32}"
        r"|"
        r"[0-9a-fA-F]{8}-"
        r"[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{12}"
        r")"
    )

    def to_python(self, value: str) -> str:
        # normalize to dashed, validates both formats
        return str(uuid.UUID(value))

    def to_url(self, value) -> str:
        return str(value)


class UUIDAnyOrFKConverter:
    regex = rf"(?:__fk__|{UUIDAnyConverter.regex})"

    def to_python(self, value: str) -> str:
        if value == "__fk__":
            return value
        return str(uuid.UUID(value))

    def to_url(self, value) -> str:
        return str(value)
