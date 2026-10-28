package club.lang.resources;

/** One read-only recovery of an absent child; a changed parent is never accepted. */
public final class StableChildRecovery {
    private StableChildRecovery() {}
    public interface Port<T> {
        void check();
        Object state();
        boolean refresh();
        T read();
        default void trace(int result) {}
    }
    public static <T> T recover(Port<T> port) {
        port.check();
        Object before = port.state();
        if (before == null) { port.trace(1); return null; }
        if (!port.refresh()) { port.trace(2); return null; }
        port.check();
        Object after = port.state();
        if (!before.equals(after)) { port.trace(3); return null; }
        // No input, no loop, and no recursive retry. The caller must still scan
        // this child and verify the complete observation against the original frame.
        T child = port.read();
        port.trace(child == null ? 4 : 5);
        return child;
    }
}
