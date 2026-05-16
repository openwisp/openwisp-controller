import uuid


class UUIDAnyConverter:
    """
    Matches a UUID string in either dashed (standard) or hex (no-dash) format.
    Used to ensure backward compatibility with devices or external systems
    that may send UUIDs without dashes.
    """

    regex = (
        r"(?:"
        r"[0-9a-f]{32}"
        r"|"
        r"[0-9a-f]{8}-"
        r"[0-9a-f]{4}-"
        r"[0-9a-f]{4}-"
        r"[0-9a-f]{4}-"
        r"[0-9a-f]{12}"
        r")"
    )

    def to_python(self, value: str) -> str:
        if value != value.lower():
            raise ValueError("UUID must be lowercase")
        return str(uuid.UUID(value))

    def to_url(self, value) -> str:
        return str(value)
