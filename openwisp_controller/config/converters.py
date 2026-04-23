import uuid


class UUIDAnyConverter:
    """
    Matches a UUID string in either dashed (standard) or hex (no-dash) format.
    Used to ensure backward compatibility with devices or external systems
    that may send UUIDs without dashes.
    """

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
        return str(uuid.UUID(value))

    def to_url(self, value) -> str:
        return str(value)
