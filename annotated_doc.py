"""
Annotated Doc compatibility module.

Provides the Doc annotation for FastAPI documentation.
Uses typing_extensions.Doc when available (Python 3.9+ with typing_extensions >= 4.9.0),
otherwise provides a simple fallback implementation.
"""

try:
    from typing_extensions import Doc
except ImportError:
    class Doc:
        """
        Documentation annotation for Annotated types.

        Used to provide documentation for type annotations in FastAPI endpoints.
        Falls back to a simple implementation if typing_extensions is not available.

        Example:
            from typing import Annotated
            from annotated_doc import Doc

            def endpoint(
                user_id: Annotated[str, Doc("The user's unique identifier")]
            ):
                pass
        """
        __slots__ = ('documentation',)

        def __init__(self, documentation: str) -> None:
            self.documentation = documentation

        def __repr__(self) -> str:
            return f"Doc({self.documentation!r})"

        def __hash__(self) -> int:
            return hash(self.documentation)

        def __eq__(self, other: object) -> bool:
            if isinstance(other, Doc):
                return self.documentation == other.documentation
            return NotImplemented


__all__ = ['Doc']
