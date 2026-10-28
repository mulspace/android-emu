import club.lang.resources.SnapshotCapture;
import java.util.*;

/** Compile against the exact candidate SnapshotCapture.java, not a behavior mock. */
public final class CheckedCaptureProbe {
    static SnapshotCapture.Observation a = new SnapshotCapture.Observation("app:720:1560:0", "original", false);
    static SnapshotCapture.Observation b = new SnapshotCapture.Observation("app:720:1560:0", "changed", false);
    static SnapshotCapture.Observation moved = new SnapshotCapture.Observation("app:1560:720:1", "original", false);
    static SnapshotCapture.Observation sensitive = new SnapshotCapture.Observation("app:720:1560:0", "original", true);
    static void check(boolean value) { if(!value) throw new AssertionError(); }
    static final class Port implements SnapshotCapture.Port<String> {
        final List<Object> reads; int images, discarded, pauses;
        Port(Object... values) { reads = new ArrayList<>(Arrays.asList(values)); }
        public SnapshotCapture.Observation observe() throws Exception {
            Object value = reads.remove(0);
            if(value instanceof Exception) throw (Exception)value;
            return (SnapshotCapture.Observation)value;
        }
        public String capture() { return "image-" + ++images; }
        public void discard(String value) { discarded++; }
        public void pause() { pauses++; }
    }
    static SnapshotCapture.IncompleteHierarchy absent() { return new SnapshotCapture.IncompleteHierarchy(); }
    static void rejects(Port p, Class<? extends Exception> expected) throws Exception {
        try { SnapshotCapture.stable(p, a); throw new AssertionError("accepted invalid capture"); }
        catch(Exception error) { if(!expected.isInstance(error)) throw error; }
    }
    public static void main(String[] args) throws Exception {
        Port p=new Port(absent(),a,a);
        check(SnapshotCapture.stable(p,a).equals("image-1")); check(p.images==1 && p.discarded==0 && p.pauses==1);
        p=new Port(a,absent(),a,a);
        check(SnapshotCapture.stable(p,a).equals("image-2")); check(p.images==2 && p.discarded==1 && p.pauses==1);
        p=new Port(absent(),b,b); rejects(p,SnapshotCapture.Mismatch.class);
        check(p.images==0 && p.pauses==1); // The original expected tree was NOT replaced.
        p=new Port(a,b); rejects(p,SnapshotCapture.Mismatch.class); check(p.discarded==1 && p.pauses==0);
        p=new Port(a,moved); rejects(p,SnapshotCapture.UnstableSurface.class); check(p.discarded==1 && p.pauses==0);
        p=new Port(sensitive); rejects(p,IllegalStateException.class); check(p.images==0 && p.pauses==0);
        p=new Port(a,sensitive); rejects(p,IllegalStateException.class); check(p.discarded==1 && p.pauses==0);
        p=new Port(absent(),absent(),absent()); rejects(p,SnapshotCapture.IncompleteHierarchy.class);
        check(p.images==0 && p.pauses==2 && p.reads.isEmpty());
        p=new Port(new java.io.IOException("transport")); rejects(p,java.io.IOException.class);
        check(p.images==0 && p.pauses==0);
        p=new Port(a,a); check(SnapshotCapture.stable(p,a).equals("image-1")); check(p.pauses==0);
        System.out.println("checked capture: 10 scenarios passed; original expected frame preserved");
    }
}
