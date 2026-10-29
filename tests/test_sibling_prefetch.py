import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which("javac") and shutil.which("java"),"JDK required")
class SiblingPrefetchContract(unittest.TestCase):
    def test_framework_identity_ownership_and_unsupported_contexts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            sources={
                "android/os/Build.java": "package android.os; public final class Build { public static class VERSION { public static int SDK_INT=24; } }",
                "android/view/accessibility/AccessibilityNodeInfo.java": r'''package android.view.accessibility;
public class AccessibilityNodeInfo {
    public int count=1,window=7,reads,recycled; public long source=42,lastId=-1;
    public boolean sealed=true,failRead,failIdentity; public AccessibilityNodeInfo answer;
    public int getChildCount(){return count;}
    public int getWindowId(){return window;}
    public void recycle(){recycled++;}
    private void enforceSealed(){if(!sealed)throw new IllegalStateException("private details");}
    public long getChildId(int index){if(index!=0)throw new IndexOutOfBoundsException();return 42;}
    public long getSourceNodeId(){if(failIdentity)throw new IllegalStateException("private details");return source;}
    private AccessibilityNodeInfo getNodeForAccessibilityId(long id){reads++;lastId=id;if(failRead)throw new IllegalStateException("private details");return answer;}
}''',
                "Probe.java": r'''import club.lang.resources.SiblingPrefetch;
import android.view.accessibility.AccessibilityNodeInfo;
import android.os.Build;
public class Probe {
    static void check(boolean x){if(!x)throw new AssertionError();}
    static void fails(Runnable r){try{r.run();throw new AssertionError();}catch(IllegalStateException e){check(!e.toString().contains("private details"));check(e.getCause()==null);}}
    public static void main(String[] args){
        AccessibilityNodeInfo p=new AccessibilityNodeInfo(),c=new AccessibilityNodeInfo();p.answer=c;
        check(SiblingPrefetch.child(p,0)==c);check(p.lastId==42 && p.reads==1 && c.recycled==0);
        p.answer=null;check(SiblingPrefetch.child(p,0)==null);p.answer=c;
        c.source=99;fails(()->SiblingPrefetch.child(p,0));check(c.recycled==1);c.source=42;
        c.window=8;fails(()->SiblingPrefetch.child(p,0));check(c.recycled==2);c.window=7;
        c.failIdentity=true;fails(()->SiblingPrefetch.child(p,0));check(c.recycled==3);c.failIdentity=false;
        int reads=p.reads;p.sealed=false;fails(()->SiblingPrefetch.child(p,0));check(p.reads==reads);p.sealed=true;
        fails(()->SiblingPrefetch.child(p,-1));fails(()->SiblingPrefetch.child(p,1));fails(()->SiblingPrefetch.child(null,0));check(p.reads==reads);
        Build.VERSION.SDK_INT=25;fails(()->SiblingPrefetch.child(p,0));check(p.reads==reads);Build.VERSION.SDK_INT=24;
        p.failRead=true;fails(()->SiblingPrefetch.child(p,0));check(c.recycled==3);
    }
}'''
            }
            for name,body in sources.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body)
            subprocess.run(["javac","-d",folder,str(ROOT/"experimental/native/SiblingPrefetch.java"),*[str(root/name) for name in sources]],check=True,timeout=30)
            subprocess.run(["java","-cp",folder,"Probe"],check=True,timeout=15)
