import club.lang.resources.HierarchyDifference;

public final class HierarchyDifferenceProbe {
    static String tree(String nodes){return "<hierarchy rotation=\"0\">"+nodes+"</hierarchy>";}
    static String node(String text){return "<node package=\"fixture\" text=\""+text+"\" bounds=\"[0,0][10,10]\"></node>";}
    static String clock(String time){return "<node package=\"com.android.systemui\" resource-id=\"com.android.systemui:id/clock\" class=\"android.widget.TextView\" clickable=\"false\" password=\"false\" text=\""+time+"\" content-desc=\"time "+time+"\"></node>";}
    static void check(boolean value){if(!value)throw new AssertionError();}
    static void has(String result,String text){check(result.contains(text));}
    public static void main(String[] args) {
        String a=tree(clock("7:08")+node("PRIVATE-ORIGINAL"));
        String b=tree(clock("7:09")+node("PRIVATE-ORIGINAL"));
        String diff=HierarchyDifference.describe(a,b);
        has(diff,"clock_value_only=1");has(diff,"changed_nodes=1");has(diff,"text=1");has(diff,"description=1");
        check(!diff.contains("PRIVATE") && !diff.contains("7:08") && !diff.contains("systemui"));
        diff=HierarchyDifference.describe(a,b.replace("PRIVATE-ORIGINAL","PRIVATE-CHANGED"));
        has(diff,"clock_value_only=0");has(diff,"changed_nodes=2");has(diff,"text=2");
        has(HierarchyDifference.describe(a,a.replace("[0,0][10,10]","[1,1][11,11]")),"bounds=1");
        has(HierarchyDifference.describe(a,tree(node("PRIVATE-ORIGINAL"))),"structure_changed=1");
        has(HierarchyDifference.describe(a,a.replace("package=\"fixture\"","package=\"other\"")),"identity=1");
        has(HierarchyDifference.describe(a,a.replace("clickable=\"false\"","clickable=\"true\"")),"flags=1");
        diff=HierarchyDifference.describe(a,a);has(diff,"changed_nodes=0");has(diff,"clock_value_only=0");
        has(HierarchyDifference.describe(null,a),"difference_unavailable=1");
        has(HierarchyDifference.describe(new String(new char[1000001]),a),"difference_unavailable=1");
        // Tree topology changes must not masquerade as a clock-only difference.
        a=tree("<node>"+clock("7:08")+"</node>");
        b=tree("<node></node>"+clock("7:09"));
        diff=HierarchyDifference.describe(a,b);has(diff,"structure_changed=1");has(diff,"clock_value_only=0");
        // Unknown attribute names/values are counted but never printed.
        diff=HierarchyDifference.describe(tree(node("x")),tree(node("x").replace("text=", "private-name=\"PRIVATE-VALUE\" text=")));
        has(diff,"other=1");check(!diff.contains("private-name") && !diff.contains("PRIVATE-VALUE"));
        System.out.println("numeric hierarchy difference: 11 scenarios passed");
    }
}
