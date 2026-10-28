package club.lang.resources;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Experimental complete, single traversal; no Android input or hidden-node shortcut. */
public final class SinglePassHierarchy {
    private SinglePassHierarchy() {}
    public static final class IncompleteHierarchy extends IllegalStateException {
        public final int depth, index, visited;
        IncompleteHierarchy(int depth, int index, int visited) {
            this.depth=depth; this.index=index; this.visited=visited;
        }
    }
    public interface Node {
        boolean visible();
        boolean password();
        int inputType();
        int childCount();
        Node child(int index);
        Map<String, String> attributes();
        void recycle();
    }
    public interface Check { void alive() throws Exception; }
    public static final class Result {
        public String xml;
        public int nodeCount;
        public final List<Map<String,String>> sensitive = new ArrayList<>();
    }
    private static final String[] KEYS = {"text", "resource-id", "class", "package",
        "content-desc", "checkable", "checked", "clickable", "enabled", "focusable",
        "focused", "scrollable", "long-clickable", "password", "selected", "bounds", "hint"};

    private static void escaped(StringBuilder out, String value) {
        if (value == null) throw new IllegalStateException();
        for (int offset=0;offset<value.length();) {
            int cp=value.codePointAt(offset); offset+=Character.charCount(cp);
            if (cp=='&') out.append("&amp;");
            else if(cp=='<')out.append("&lt;");
            else if(cp=='>')out.append("&gt;");
            else if(cp=='\"')out.append("&quot;");
            else if(cp=='\n')out.append("&#10;");
            else if(cp=='\r')out.append("&#13;");
            else if(cp=='\t')out.append("&#9;");
            else if(cp>=32 && cp<=0x10ffff && !(cp>=0xd800 && cp<=0xdfff) && cp!=0xfffe && cp!=0xffff)
                out.appendCodePoint(cp);
            else throw new IllegalStateException();
            if(out.length()>1000000)throw new IllegalStateException();
        }
    }

    public static Result capture(List<Node> roots, int rotation, Check check) throws Exception {
        Result result=new Result();
        StringBuilder xml=new StringBuilder("<?xml version=\"1.0\" encoding=\"UTF-8\"?><hierarchy rotation=\"")
            .append(rotation).append("\">");
        if(roots==null || roots.isEmpty() || rotation<0 || rotation>3)throw new IllegalStateException();
        // Root ownership remains with the caller; every obtained child is released here.
        for(Node root:roots) visit(root,0,0,true,check,result,xml);
        xml.append("</hierarchy>");
        if(xml.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8).length>1000000)
            throw new IllegalStateException();
        result.xml=xml.toString();
        return result;
    }

    private static void visit(Node node,int depth,int index,boolean render,Check check,
                              Result result,StringBuilder xml)throws Exception {
        check.alive();
        if(node==null)throw new IncompleteHierarchy(depth,index,result.nodeCount);
        if(depth>80 || ++result.nodeCount>10000)throw new IllegalStateException();
        boolean visible=node.visible();
        int input=node.inputType(), kind=input&15, variation=input&4080;
        boolean secret=visible && (node.password()
            || (kind==1 && (variation==128 || variation==144 || variation==224))
            || (kind==2 && variation==16));
        Map<String,String> attrs=(render || secret)?node.attributes():null;
        if(secret)result.sensitive.add(attrs);
        if(render) {
            xml.append("<node index=\"").append(index).append('"');
            for(String key:KEYS) {
                if(key.equals("hint") && !attrs.containsKey(key))continue;
                xml.append(' ').append(key).append("=\"");
                escaped(xml,secret && (key.equals("text") || key.equals("content-desc") || key.equals("hint"))?"":attrs.get(key));
                xml.append('"');
            }
            xml.append('>');
            if(xml.length()>1000000)throw new IllegalStateException();
        }
        int count=node.childCount();
        if(count<0 || count>10000)throw new IllegalStateException();
        for(int childIndex=0;childIndex<count;childIndex++) {
            check.alive();
            Node child=node.child(childIndex);
            if(child==null)throw new IncompleteHierarchy(depth+1,childIndex,result.nodeCount);
            try { visit(child,depth+1,childIndex,render && child.visible(),check,result,xml); }
            finally { child.recycle(); }
        }
        if(render)xml.append("</node>");
    }
}
