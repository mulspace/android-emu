import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which("javac") and shutil.which("java"),"JDK required")
class BoundedPairReaderContract(unittest.TestCase):
    def test_parallelism_ownership_failures_deadlines_and_join(self):
        source=r"""import club.lang.resources.BoundedPairReader;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
public class Probe {
    static void check(boolean x){if(!x)throw new AssertionError();}
    static void await(CountDownLatch latch){try{check(latch.await(2,TimeUnit.SECONDS));}catch(InterruptedException e){throw new IllegalStateException();}}
    static final class Value {int recycled;}
    static final class Job implements BoundedPairReader.Job<Value> {
        final Value value=new Value();int reads,closed;boolean fail;
        Runnable run=()->{};
        public Value read(){reads++;run.run();if(fail)throw new IllegalStateException("test-only");return value;}
        public void close(){closed++;check(closed==1);}
    }
    static BoundedPairReader<Value> reader(long ms){return new BoundedPairReader<>(v->{v.recycled++;check(v.recycled==1);},ms);}
    static void fails(Runnable call){try{call.run();throw new AssertionError();}catch(IllegalStateException expected){}}
    static void sleep(long ms){try{Thread.sleep(ms);}catch(InterruptedException e){Thread.currentThread().interrupt();}}
    public static void main(String[] args)throws Exception {
        BoundedPairReader<Value> r=reader(2000);
        Job a=new Job(),b=new Job();CountDownLatch both=new CountDownLatch(2);
        a.run=()->{both.countDown();await(both);};b.run=a.run;
        BoundedPairReader.Pair<Value> pair=r.read(a,b);
        check(pair.first==a.value && pair.second==b.value);check(a.closed==1 && b.closed==1);
        check(a.value.recycled==0 && b.value.recycled==0);
        // Same reader can be reused; it never has more than one worker.
        AtomicInteger workers=new AtomicInteger(),max=new AtomicInteger();
        for(int i=0;i<8;i++) {Job c=new Job(),d=new Job();d.run=()->{max.set(Math.max(max.get(),workers.incrementAndGet()));workers.decrementAndGet();};r.read(c,d);}
        check(max.get()==1);r.close();
        Job c=new Job(),d=new Job();fails(()->r.read(c,d));check(c.closed==1 && d.closed==1 && c.reads==0 && d.reads==0);
        // Failure of the main read releases a concurrently completing result.
        BoundedPairReader<Value> r2=reader(2000);Job e=new Job(),f=new Job();CountDownLatch started=new CountDownLatch(1);
        e.run=()->{await(started);};e.fail=true;f.run=()->{started.countDown();sleep(30);};
        fails(()->r2.read(e,f));r2.close();check(e.closed==1 && f.closed==1 && f.value.recycled==1);
        // Worker failure releases the caller's successful node and shuts down.
        BoundedPairReader<Value> r3=reader(2000);Job g=new Job(),h=new Job();h.fail=true;
        fails(()->r3.read(g,h));r3.close();check(g.value.recycled==1 && g.closed==1 && h.closed==1);
        // Deadline does not lose a late node or return an unjoined worker.
        BoundedPairReader<Value> r4=reader(10);Job i=new Job(),j=new Job();CountDownLatch slow=new CountDownLatch(1);
        i.run=()->await(slow);j.run=()->{slow.countDown();sleep(80);};
        fails(()->r4.read(i,j));r4.close();check(i.value.recycled==1 && j.value.recycled==1 && j.closed==1);
        // Interruption is preserved, but close waits for ownership cleanup.
        BoundedPairReader<Value> r5=reader(2000);Job k=new Job(),l=new Job();CountDownLatch wait=new CountDownLatch(1);
        k.run=()->{await(wait);Thread.currentThread().interrupt();};l.run=()->{wait.countDown();sleep(40);};
        fails(()->r5.read(k,l));r5.close();check(Thread.interrupted());check(k.value.recycled==1 && l.value.recycled==1);
        // No leaked live workers after any completed/failed capture.
        for(Thread thread:Thread.getAllStackTraces().keySet())check(!thread.isAlive() || !thread.getName().equals("emu-child-read"));
    }
}
"""
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"Probe.java";p.write_text(source)
            subprocess.run(["javac","-Xlint:unchecked","-d",folder,str(ROOT/"experimental/native/BoundedPairReader.java"),str(p)],check=True,timeout=30)
            subprocess.run(["java","-cp",folder,"Probe"],check=True,timeout=15)
