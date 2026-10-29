import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which("javac") and shutil.which("java"),"JDK required")
class ParallelChildrenContract(unittest.TestCase):
    def test_parent_copies_identity_and_recycling(self):
        sources={
            "android/os/Build.java":"package android.os; public class Build {public static class VERSION {public static int SDK_INT=24;}}",
            "android/view/accessibility/AccessibilityNodeInfo.java":r"""package android.view.accessibility;
import java.util.concurrent.atomic.AtomicInteger;
public class AccessibilityNodeInfo {
    public static final AtomicInteger copies=new AtomicInteger(),closedCopies=new AtomicInteger(),closedChildren=new AtomicInteger();
    public int window=7;public long source=10;public boolean copy,wrong,sealed=true;public int closed;
    public static AccessibilityNodeInfo obtain(AccessibilityNodeInfo p){AccessibilityNodeInfo v=new AccessibilityNodeInfo();v.window=p.window;v.source=p.source;v.wrong=p.wrong;v.sealed=p.sealed;v.copy=true;copies.incrementAndGet();return v;}
    public int getChildCount(){return 2;}
    public int getWindowId(){return window;}
    public long getChildId(int index){return 100+index;}
    public long getSourceNodeId(){return source;}
    private void enforceSealed(){if(!sealed)throw new IllegalStateException();}
    private AccessibilityNodeInfo getNodeForAccessibilityId(long id){if(!copy)throw new AssertionError();AccessibilityNodeInfo n=new AccessibilityNodeInfo();n.source=wrong ? 99 : id;return n;}
    public void recycle(){if(++closed!=1)throw new AssertionError();if(copy)closedCopies.incrementAndGet();else closedChildren.incrementAndGet();}
}
""",
            "Probe.java":r"""import club.lang.resources.*;
import android.view.accessibility.AccessibilityNodeInfo;
public class Probe {
    static void check(boolean b){if(!b)throw new AssertionError();}
    public static void main(String[] args){
        AccessibilityNodeInfo p=new AccessibilityNodeInfo();
        try(ParallelChildren reader=new ParallelChildren()) {
            BoundedPairReader.Pair<AccessibilityNodeInfo> pair=reader.read(p,0);
            check(pair.first.source==100 && pair.second.source==101 && p.closed==0);
            check(AccessibilityNodeInfo.closedCopies.get()==2);
            pair.first.recycle();pair.second.recycle();
        }
        p.wrong=true;
        try(ParallelChildren reader=new ParallelChildren()) {
            try{reader.read(p,0);throw new AssertionError();}catch(IllegalStateException expected){}
        }
        check(AccessibilityNodeInfo.copies.get()==AccessibilityNodeInfo.closedCopies.get());check(p.closed==0);
        try(ParallelChildren reader=new ParallelChildren()) {
            try{reader.read(p,1);throw new AssertionError();}catch(IllegalArgumentException expected){}
        }
        check(AccessibilityNodeInfo.copies.get()==4);
    }
}
"""}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name,body in sources.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body)
            files=[ROOT/"experimental/native"/name for name in ("SiblingPrefetch.java","ParallelChildren.java","BoundedPairReader.java")]
            subprocess.run(["javac","-Xlint:unchecked","-d",folder,*map(str,files),*[str(root/name) for name in sources]],check=True,timeout=30)
            subprocess.run(["java","-cp",folder,"Probe"],check=True,timeout=15)
