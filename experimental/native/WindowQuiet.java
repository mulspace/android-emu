package club.lang.resources;

/** Bounded scheduling hint only; never evidence that a page is safe or ready. */
public final class WindowQuiet {
    private WindowQuiet() {}
    public interface Port {
        long now();
        void alive() throws Exception;
        String windows() throws Exception;
        void pause(long milliseconds) throws Exception;
    }
    public static long await(Port port,long quietMs,long limitMs) throws Exception {
        if(quietMs<100 || quietMs>2000 || limitMs<quietMs || limitMs>10000)
            throw new IllegalArgumentException();
        long start=port.now(), previousTime=start, changedAt=start;
        String previous=null;
        while(true) {
            port.alive();
            long before=port.now();
            if(before<previousTime)throw new IllegalStateException("Clock regressed");
            if(before-start>=limitMs)throw new java.util.concurrent.TimeoutException("Window transition did not settle");
            String current=port.windows();
            port.alive();
            long now=port.now();
            if(now<before)throw new IllegalStateException("Clock regressed");
            // A response arriving after the bound is never accepted.
            if(now-start>=limitMs)throw new java.util.concurrent.TimeoutException("Window transition did not settle");
            if(current==null || current.isEmpty()) {previous=null;changedAt=now;}
            else if(!current.equals(previous)) {previous=current;changedAt=now;}
            else if(now-changedAt>=quietMs)return now-start;
            previousTime=now;
            port.pause(Math.min(100,limitMs-(now-start)));
        }
    }
}
