from collections import defaultdict, deque
from datetime import datetime, timedelta


class LoginRateLimiter:
    def __init__(self, max_attempts=5, window_seconds=900):
        self.max_attempts = max_attempts
        self.window = timedelta(seconds=window_seconds)
        self._attempts = defaultdict(deque)

    def is_limited(self, key):
        now = datetime.utcnow()
        attempts = self._attempts[key]
        self._prune(attempts, now)
        return len(attempts) >= self.max_attempts

    def record_failure(self, key):
        now = datetime.utcnow()
        attempts = self._attempts[key]
        self._prune(attempts, now)
        attempts.append(now)

    def reset(self, key):
        self._attempts.pop(key, None)

    def _prune(self, attempts, now):
        while attempts and now - attempts[0] > self.window:
            attempts.popleft()


def login_rate_key(prefix, identifier, remote_addr):
    normalized_identifier = (identifier or "").strip().lower()
    normalized_addr = remote_addr or "unknown"
    return f"{prefix}:{normalized_addr}:{normalized_identifier}"


def login_ip_key(prefix, remote_addr):
    normalized_addr = remote_addr or "unknown"
    return f"{prefix}:ip:{normalized_addr}"


admin_login_limiter = LoginRateLimiter()
employee_login_limiter = LoginRateLimiter()
admin_ip_login_limiter = LoginRateLimiter(max_attempts=20, window_seconds=900)
employee_ip_login_limiter = LoginRateLimiter(max_attempts=30, window_seconds=900)
