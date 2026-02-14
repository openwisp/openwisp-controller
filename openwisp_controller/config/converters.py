import uuid


class UUIDAnyConverter:
    """
    Matches a UUID string in either dashed (standard) or hex (no-dash) format.
    Used to ensure backward compatibility with devices or external systems
    that may send UUIDs without dashes.
    """

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
    """
    Matches a UUID (dashed or hex) OR the literal string '__fk__'.
    The '__fk__' literal is used as a placeholder in admin URLs where a
    real object ID is not yet available.
    """

    regex = rf"(?:__fk__|{UUIDAnyConverter.regex})"

    def to_python(self, value: str) -> str:
        if value == "__fk__":
            return value
        return str(uuid.UUID(value))

    def to_url(self, value) -> str:
        return str(value)
