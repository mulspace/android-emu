package club.lang.resources;

import android.os.Build;
import android.view.accessibility.AccessibilityNodeInfo;
import java.lang.reflect.Method;

/** API-24-only diagnostic: same framework connection, with sibling prefetch.
 * Complete traversal, cache invalidation and snapshot guards remain unchanged.
 */
public final class SiblingPrefetch {
    private SiblingPrefetch() {}
    private static final class Api24 {
        static final Method SEALED=method("enforceSealed");
        static final Method CHILD_ID=method("getChildId",int.class);
        static final Method SOURCE_ID=method("getSourceNodeId");
        static final Method RELATED=method("getNodeForAccessibilityId",long.class);
        static Method method(String name,Class<?>...parameters) {
            try {
                Method result=AccessibilityNodeInfo.class.getDeclaredMethod(name,parameters);
                result.setAccessible(true);
                return result;
            } catch(Exception error) { throw new IllegalStateException("Unsupported diagnostic framework"); }
        }
    }
    public static AccessibilityNodeInfo child(AccessibilityNodeInfo parent,int index) {
        if(Build.VERSION.SDK_INT!=24 || parent==null || index<0 || index>=parent.getChildCount())
            throw new IllegalStateException("Unsupported diagnostic node");
        AccessibilityNodeInfo result=null;
        boolean returned=false;
        try {
            Api24.SEALED.invoke(parent);
            long id=(Long)Api24.CHILD_ID.invoke(parent,index);
            // Android 7's existing method checks its connection and prefetches
            // predecessors + siblings + descendants through the normal client.
            result=(AccessibilityNodeInfo)Api24.RELATED.invoke(parent,id);
            if(result!=null && ((Long)Api24.SOURCE_ID.invoke(result)!=id || result.getWindowId()!=parent.getWindowId())) {
                throw new IllegalStateException("Unexpected diagnostic child identity");
            }
            returned=true;
            return result;
        } catch(Exception error) { throw new IllegalStateException("Diagnostic child lookup failed"); }
        finally { if(result!=null && !returned)result.recycle(); }
    }
}
