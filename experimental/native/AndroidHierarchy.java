package club.lang.resources;

import android.app.UiAutomation;
import android.graphics.Rect;
import android.os.Build;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.json.JSONArray;
import org.json.JSONObject;

/** Isolated experiment: preserve all windows and scan even invisible descendants. */
public final class AndroidHierarchy {
    private AndroidHierarchy() {}
    public static final class Result {
        public final String xml;
        public final int nodes;
        public final JSONArray sensitive = new JSONArray();
        Result(SinglePassHierarchy.Result value) throws Exception {
            xml=value.xml;nodes=value.nodeCount;
            for(Map<String,String> row:value.sensitive) {
                java.util.regex.Matcher bounds=java.util.regex.Pattern.compile("\\[(-?\\d+),(-?\\d+)\\]\\[(-?\\d+),(-?\\d+)\\]").matcher(row.get("bounds"));
                if(!bounds.matches())throw new IllegalStateException();
                JSONArray coordinates=new JSONArray();
                for(int i=1;i<=4;i++)coordinates.put(Integer.parseInt(bounds.group(i)));
                sensitive.put(new JSONObject().put("package",row.get("package"))
                    .put("resource_id",row.get("resource-id")).put("bounds",coordinates));
            }
        }
    }
    private static String text(CharSequence value){return value==null?"":value.toString();}
    private static final class Node implements SinglePassHierarchy.Node {
        final AccessibilityNodeInfo node; final int width,height;
        Node(AccessibilityNodeInfo node,int w,int h){this.node=node;width=w;height=h;}
        public boolean visible(){return node.isVisibleToUser();}
        public boolean password(){return node.isPassword();}
        public int inputType(){return node.getInputType();}
        public int childCount(){return node.getChildCount();}
        public SinglePassHierarchy.Node child(int index){AccessibilityNodeInfo child=node.getChild(index);return child==null?null:new Node(child,width,height);}
        public void recycle(){node.recycle();}
        public Map<String,String> attributes(){
            Map<String,String> out=new LinkedHashMap<>();
            out.put("text",text(node.getText()));out.put("resource-id",text(node.getViewIdResourceName()));
            out.put("class",text(node.getClassName()));out.put("package",text(node.getPackageName()));
            out.put("content-desc",text(node.getContentDescription()));
            out.put("checkable",String.valueOf(node.isCheckable()));out.put("checked",String.valueOf(node.isChecked()));
            out.put("clickable",String.valueOf(node.isClickable()));out.put("enabled",String.valueOf(node.isEnabled()));
            out.put("focusable",String.valueOf(node.isFocusable()));out.put("focused",String.valueOf(node.isFocused()));
            out.put("scrollable",String.valueOf(node.isScrollable()));out.put("long-clickable",String.valueOf(node.isLongClickable()));
            out.put("password",String.valueOf(node.isPassword()));out.put("selected",String.valueOf(node.isSelected()));
            Rect bounds=new Rect();node.getBoundsInScreen(bounds);
            if(!bounds.intersect(0,0,width,height))bounds.setEmpty();
            out.put("bounds",bounds.toShortString());
            if(Build.VERSION.SDK_INT>=26)out.put("hint",Api26.hint(node));
            return out;
        }
    }
    private static final class Api26 {
        static String hint(AccessibilityNodeInfo node){return text(node.getHintText());}
    }
    public static Result capture(UiAutomation automation,int rotation,int width,int height,
                                 SinglePassHierarchy.Check check)throws Exception {
        Set<AccessibilityNodeInfo> owned=new LinkedHashSet<>();
        List<AccessibilityWindowInfo> windows=null;
        try {
            check.alive();
            AccessibilityNodeInfo active=automation.getRootInActiveWindow();
            if(active==null)throw new SnapshotCapture.IncompleteHierarchy();
            owned.add(active);
            windows=automation.getWindows();
            if(windows!=null)for(AccessibilityWindowInfo window:windows) {
                check.alive();
                AccessibilityNodeInfo root=window.getRoot();
                if(root==null)throw new SnapshotCapture.IncompleteHierarchy();
                if(!owned.add(root)) {
                    boolean same=false;for(AccessibilityNodeInfo existing:owned)if(existing==root)same=true;
                    if(!same)root.recycle();
                }
            }
            List<SinglePassHierarchy.Node> roots=new ArrayList<>();
            for(AccessibilityNodeInfo root:owned)roots.add(new Node(root,width,height));
            return new Result(SinglePassHierarchy.capture(roots,rotation,check));
        } catch(SinglePassHierarchy.IncompleteHierarchy error) {
            throw new SnapshotCapture.IncompleteHierarchy();
        } finally {
            for(AccessibilityNodeInfo root:owned)root.recycle();
            if(windows!=null)for(AccessibilityWindowInfo window:windows)window.recycle();
        }
    }
}
