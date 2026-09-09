from slowapi import Limiter
from slowapi.util import get_remote_address

# Generous enough that legitimate multi-check-in test/usage flows never
# hit it, but real protection against credential-stuffing / check-in spam
# (REQUIREMENTS.md: rate limiting on login and check-in endpoints).
limiter = Limiter(key_func=get_remote_address)
