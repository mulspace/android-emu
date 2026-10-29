"""Probe-only startup timings; no payloads, new deadlines or retries."""
import time


def traced_session_type(base, emit):
    class TracedSession(base):
        async def start(self, session):
            original = self.transport.start
            async def launch(nonce):
                tick, ok = time.monotonic(), False
                try:
                    result = await original(nonce)
                    ok = True
                    return result
                finally:
                    emit({"phase": "native_transport_start", "ok": ok,
                          "seconds": round(time.monotonic() - tick, 3)})
            self.transport.start = launch
            try:
                return await super().start(session)
            finally:
                self.transport.start = original

        async def _read(self, *args, **kwargs):
            if self.ready:
                return await super()._read(*args, **kwargs)
            phase = "native_ready_wait" if self.sequence == 0 else "native_configure_wait"
            tick, ok = time.monotonic(), False
            try:
                result = await super()._read(*args, **kwargs)
                ok = True
                return result
            finally:
                emit({"phase": phase, "ok": ok,
                      "seconds": round(time.monotonic() - tick, 3)})
    return TracedSession
