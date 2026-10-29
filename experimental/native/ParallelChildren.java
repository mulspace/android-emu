package club.lang.resources;

import android.view.accessibility.AccessibilityNodeInfo;

/** API-24 opt-in. Each normal framework read owns an immutable parent copy. */
public final class ParallelChildren implements AutoCloseable {
    private final BoundedPairReader<AccessibilityNodeInfo> reader =
        new BoundedPairReader<>(AccessibilityNodeInfo::recycle,6000);
    private static BoundedPairReader.Job<AccessibilityNodeInfo> job(AccessibilityNodeInfo parent,int index) {
        final AccessibilityNodeInfo copy=AccessibilityNodeInfo.obtain(parent);
        return new BoundedPairReader.Job<AccessibilityNodeInfo>() {
            public AccessibilityNodeInfo read(){return SiblingPrefetch.child(copy,index);}
            public void close(){copy.recycle();}
        };
    }
    public BoundedPairReader.Pair<AccessibilityNodeInfo> read(AccessibilityNodeInfo parent,int index) {
        if(parent==null || index<0 || index+1>=parent.getChildCount())throw new IllegalArgumentException();
        BoundedPairReader.Job<AccessibilityNodeInfo> first=job(parent,index),second;
        try { second=job(parent,index+1); }
        catch(RuntimeException error){first.close();throw error;}
        return reader.read(first,second);
    }
    public void close(){reader.close();}
}
