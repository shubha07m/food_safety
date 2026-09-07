from .models import DerivedContext


def contextualize():
    # No inference from names, cuisine or neighbourhood. Explicit review is required.
    return DerivedContext()
