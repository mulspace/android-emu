package club.lang.resources;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Numeric diagnostics only. Never used for snapshot equality or acceptance. */
public final class HierarchyDifference {
    private HierarchyDifference() {}
    private static final Pattern NODE = Pattern.compile("<node\\b[^>]*>");
    private static final Pattern ATTRIBUTE = Pattern.compile("([a-z][a-z0-9-]*)=\"([^\"]*)\"");
    private static final String[] GROUPS = {"text", "description", "bounds", "identity", "flags", "other"};
    private static List<Map<String,String>> nodes(String xml) {
        if (xml == null || xml.length() > 1000000 || !xml.contains("<hierarchy"))
            throw new IllegalArgumentException();
        List<Map<String,String>> out = new ArrayList<>();
        Matcher nodes = NODE.matcher(xml);
        while(nodes.find()) {
            if(out.size() >= 10000) throw new IllegalArgumentException();
            Map<String,String> attrs = new HashMap<>();
            Matcher values = ATTRIBUTE.matcher(nodes.group());
            while(values.find()) {
                if(attrs.put(values.group(1), values.group(2)) != null)
                    throw new IllegalArgumentException();
            }
            out.add(attrs);
        }
        return out;
    }
    private static int group(String key) {
        if(key.equals("text")) return 0;
        if(key.equals("content-desc") || key.equals("hint")) return 1;
        if(key.equals("bounds")) return 2;
        if(key.equals("resource-id") || key.equals("class") || key.equals("package") || key.equals("index")) return 3;
        if(key.equals("checkable") || key.equals("checked") || key.equals("clickable") || key.equals("enabled")
                || key.equals("focusable") || key.equals("focused") || key.equals("scrollable")
                || key.equals("long-clickable") || key.equals("password") || key.equals("selected")) return 4;
        return 5;
    }
    private static boolean clock(Map<String,String> node) {
        return "com.android.systemui".equals(node.get("package"))
            && "com.android.systemui:id/clock".equals(node.get("resource-id"))
            && "android.widget.TextView".equals(node.get("class"))
            && "false".equals(node.get("clickable")) && "false".equals(node.get("password"));
    }
    public static String describe(String left, String right) {
        try {
            List<Map<String,String>> a = nodes(left), b = nodes(right);
            int changed=0, clocks=0; int[] counts = new int[GROUPS.length];
            boolean structure = a.size()!=b.size() || !NODE.matcher(left).replaceAll("<node>")
                .equals(NODE.matcher(right).replaceAll("<node>"));
            for(int i=0;i<Math.min(a.size(),b.size());i++) {
                Map<String,String> x=a.get(i), y=b.get(i);
                if(x.equals(y)) continue;
                changed++;
                Set<String> keys=new HashSet<>(x.keySet()); keys.addAll(y.keySet());
                boolean clockValueOnly=clock(x) && clock(y);
                for(String key:keys) {
                    if(java.util.Objects.equals(x.get(key),y.get(key))) continue;
                    int kind=group(key); counts[kind]++;
                    if(kind>1) clockValueOnly=false;
                }
                if(clockValueOnly) clocks++;
            }
            StringBuilder result=new StringBuilder("left_nodes=").append(a.size())
                .append(" right_nodes=").append(b.size()).append(" changed_nodes=").append(changed)
                .append(" structure_changed=").append(structure?1:0)
                .append(" clock_value_nodes=").append(clocks)
                .append(" clock_value_only=").append(!structure && changed>0 && changed==clocks?1:0);
            for(int i=0;i<GROUPS.length;i++)result.append(' ').append(GROUPS[i]).append('=').append(counts[i]);
            return result.toString();
        } catch(RuntimeException error) { return "difference_unavailable=1"; }
    }
}
