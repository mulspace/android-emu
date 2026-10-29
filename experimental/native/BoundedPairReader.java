package club.lang.resources;

import java.util.List;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

/** Diagnostic only: one caller plus one worker; both jobs transfer ownership. */
public final class BoundedPairReader<T> implements AutoCloseable {
    public interface Job<T> { T read(); void close(); }
    public interface Disposer<T> { void dispose(T value); }
    public static final class Pair<T> {
        public final T first, second;
        Pair(T first,T second){this.first=first;this.second=second;}
    }
    private final Disposer<T> disposer;
    private final long timeoutMs;
    private final ThreadPoolExecutor worker;
    private Slot active;
    private boolean closed;
    public BoundedPairReader(Disposer<T> disposer,long timeoutMs) {
        if(disposer==null || timeoutMs<1 || timeoutMs>6000)throw new IllegalArgumentException();
        this.disposer=disposer;this.timeoutMs=timeoutMs;
        worker=new ThreadPoolExecutor(1,1,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<Runnable>(1),r->{
            Thread t=new Thread(r,"emu-child-read");t.setDaemon(true);return t;
        });
    }
    private void dispose(T value){if(value!=null)disposer.dispose(value);}
    private interface OwnedRunnable extends Runnable { void abandon(); }
    private final class Slot implements OwnedRunnable {
        final Job<T> job;
        boolean started,done,abandoned,failed;
        T value;
        Slot(Job<T> job){this.job=job;}
        public void run() {
            synchronized(this){if(abandoned)return;started=true;}
            T result=null;boolean error=false;
            try { result=job.read(); }
            catch(Throwable ignored){error=true;}
            finally { job.close(); }
            synchronized(this) {
                if(abandoned)dispose(result);else value=result;
                failed=error;done=true;notifyAll();
            }
        }
        synchronized T take(long deadline) {
            while(!done) {
                long left=deadline-System.nanoTime();
                if(left<=0)throw new IllegalStateException("Diagnostic child deadline exceeded");
                try { TimeUnit.NANOSECONDS.timedWait(this,left); }
                catch(InterruptedException error){Thread.currentThread().interrupt();throw new IllegalStateException("Diagnostic child interrupted");}
            }
            if(failed)throw new IllegalStateException("Diagnostic child lookup failed");
            T result=value;value=null;return result;
        }
        public synchronized void abandon() {
            if(abandoned)return;
            abandoned=true;
            if(!started)job.close();
            dispose(value);value=null;
        }
    }
    /** Synchronous pair boundary: no worker-owned child escapes before completion. */
    public synchronized Pair<T> read(Job<T> first,Job<T> second) {
        if(first==null || second==null)throw new IllegalArgumentException();
        if(closed){first.close();second.close();throw new IllegalStateException("Diagnostic reader closed");}
        Slot slot=new Slot(second);active=slot;
        T left=null,right=null;boolean transferred=false;
        try {
            long deadline=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(timeoutMs);
            worker.execute(slot);
            left=first.read();right=slot.take(deadline);
            transferred=true;
            return new Pair<>(left,right);
        } finally {
            first.close();slot.abandon();active=null;
            if(!transferred){dispose(left);dispose(right);closed=true;worker.shutdown();}
        }
    }
    public synchronized void close() {
        closed=true;
        if(active!=null)active.abandon();
        worker.shutdown();
        boolean interrupted=false,ended=false;
        long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(6);
        while(!ended && System.nanoTime()<deadline) {
            try { ended=worker.awaitTermination(Math.max(1,deadline-System.nanoTime()),TimeUnit.NANOSECONDS); }
            catch(InterruptedException error){interrupted=true;}
        }
        if(!ended) {
            List<Runnable> queued=worker.shutdownNow();
            for(Runnable item:queued)((OwnedRunnable)item).abandon();
        }
        if(interrupted)Thread.currentThread().interrupt();
        if(!ended)throw new IllegalStateException("Diagnostic child worker did not stop");
    }
}
