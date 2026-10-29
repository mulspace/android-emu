package club.lang.resources;

import java.io.StringReader;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.regex.Pattern;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NamedNodeMap;
import org.w3c.dom.Node;
import org.xml.sax.InputSource;
import org.xml.sax.SAXException;
import org.xml.sax.helpers.DefaultHandler;

/** Opt-in PUBLIC quote evidence only. Never an input or account-page authority.
 * Pixel values and the later XML values are deliberately not declared atomic.
 */
public final class ReadOnlyQuote {
    private ReadOnlyQuote() {}
    private static final String PKG = "com.guotai.dazhihui";
    private static final String PREFIX = PKG + ":id/";
    private static final String SURFACE = PKG + ":720:1560:0";
    private static final Set<String> VALUES = new HashSet<>(Arrays.asList(
        "current_price", "gain", "summary_value", "detail_value",
        "tv_bond_price_rate", "tv_price_or_rate_value",
        "bottom_index_price", "bottom_index_chg"));
    private static final Set<String> INDEX_NAMES = new HashSet<>(Arrays.asList(
        "上证", "深证", "创业", "创业板", "科创", "沪深300"));
    private static final Pattern NUMBER = Pattern.compile(
        "(?:--|[+-]?[0-9]+(?:\\.[0-9]+)?(?:%|万|亿)?)(?: +\\[[+-]?[0-9]+(?:\\.[0-9]+)?%\\])?");
    private static final Pattern CLOCK = Pattern.compile("(?:[01]?[0-9]|2[0-3]):[0-5][0-9]");
    private static final Pattern CLOCK_DESCRIPTION = Pattern.compile("(?:[01]?[0-9]|2[0-3]):[0-5][0-9](?: (?:AM|PM))?");

    public static final class State {
        public final String surface, xml;
        public final boolean sensitive;
        public State(String surface, String xml, boolean sensitive) {
            this.surface=surface; this.xml=xml; this.sensitive=sensitive;
        }
    }
    public interface Port<T> {
        State observe() throws Exception;
        T capture() throws Exception;
        void discard(T image);
    }
    public static final class Refused extends IllegalStateException {
        Refused() { super("Public quote observation did not satisfy the read-only contract"); }
    }
    private static void require(boolean ok) { if (!ok) throw new Refused(); }

    private static Map<String,String> attributes(Element element) {
        Map<String,String> result=new TreeMap<>();
        NamedNodeMap source=element.getAttributes();
        require(source.getLength()<=32);
        for(int i=0;i<source.getLength();i++) {
            Node attribute=source.item(i);
            require(attribute.getNodeValue().length()<=20000);
            result.put(attribute.getNodeName(),attribute.getNodeValue());
        }
        return result;
    }
    private static void append(StringBuilder out,String value) {
        out.append(value.length()).append(':').append(value);
    }
    private static final class Projection {
        final String symbol,name;
        int nodes, names, codes, periods, prices, orderBooks;
        final StringBuilder canonical=new StringBuilder();
        Projection(String symbol,String name) { this.symbol=symbol; this.name=name; }

        void node(Element element,int depth) {
            require(depth<=80 && ++nodes<=10000 && element.getTagName().equals("node"));
            Map<String,String> a=attributes(element);
            String pkg=a.get("package"),id=a.get("resource-id"),text=a.get("text");
            require((PKG.equals(pkg)||"com.android.systemui".equals(pkg))
                && "false".equals(a.get("password")) && id!=null && text!=null);
            String kind=a.get("class");
            // An input field is never part of this public quote contract, even if
            // the native sensitivity scan says it is not a password field.
            require(kind!=null && !kind.endsWith("EditText"));
            if(PKG.equals(pkg) && id.startsWith(PREFIX)) {
                String key=id.substring(PREFIX.length());
                if(key.equals("stock_code")) {require(text.equals(symbol));codes++;}
                if(key.equals("stock_name")) {require(text.equals(name));names++;}
                if(key.equals("minutes")) {
                    require(text.equals("分时") && "true".equals(a.get("selected")));periods++;
                }
                if(key.equals("five_level")) {require(text.equals("五档"));orderBooks++;}
                if(key.equals("current_price")) prices++;
                if(VALUES.contains(key)) {
                    require("android.widget.TextView".equals(kind)
                        && text.length()<=64 && NUMBER.matcher(text).matches()
                        && "".equals(a.get("content-desc")));
                    a.put("text","<live-number>");
                } else if(key.equals("bottom_index_name")) {
                    require("android.widget.TextView".equals(kind) && INDEX_NAMES.contains(text)
                        && "".equals(a.get("content-desc")));
                    a.put("text","<rotating-public-index>");
                }
            } else if("com.android.systemui".equals(pkg)
                    && "com.android.systemui:id/clock".equals(id)) {
                String description=a.get("content-desc");
                require("android.widget.TextView".equals(kind)
                    && "false".equals(a.get("clickable")) && CLOCK.matcher(text).matches()
                    && description!=null && (description.isEmpty() || CLOCK_DESCRIPTION.matcher(description).matches()));
                a.put("text","<clock>"); a.put("content-desc","<clock>");
            }
            canonical.append('(');
            for(Map.Entry<String,String> field:a.entrySet()) {
                append(canonical,field.getKey());append(canonical,field.getValue());
            }
            canonical.append('|');
            for(Node child=element.getFirstChild();child!=null;child=child.getNextSibling()) {
                if(child instanceof Element) node((Element)child,depth+1);
                else require(child.getNodeType()==Node.TEXT_NODE && child.getTextContent().trim().isEmpty());
            }
            canonical.append(')');
        }
    }

    /** Canonical layout/identity; never used to authorize a tap, key or text. */
    public static String project(State state,String symbol,String name) throws Exception {
        require(symbol!=null && symbol.matches("[0-9]{6}") && name!=null
            && !name.trim().isEmpty() && name.length()<=64);
        require(state!=null && !state.sensitive && SURFACE.equals(state.surface)
            && state.xml!=null && state.xml.length()<=1000000 && !state.xml.contains("<!"));
        // No DTD/entity declaration is admitted. The resolver also refuses any
        // external resource, independently of a platform parser's feature set.
        DocumentBuilderFactory factory=DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(false);factory.setValidating(false);
        DocumentBuilder parser=factory.newDocumentBuilder();
        parser.setEntityResolver((publicId,systemId)->{throw new SAXException("External XML refused");});
        parser.setErrorHandler(new DefaultHandler() {
            public void error(org.xml.sax.SAXParseException error)throws SAXException{throw error;}
            public void fatalError(org.xml.sax.SAXParseException error)throws SAXException{throw error;}
        });
        Document document=parser.parse(new InputSource(new StringReader(state.xml)));
        Element root=document.getDocumentElement();
        require(root!=null && root.getTagName().equals("hierarchy"));
        Projection projection=new Projection(symbol,name);
        for(Map.Entry<String,String> field:attributes(root).entrySet()) {
            append(projection.canonical,field.getKey());append(projection.canonical,field.getValue());
        }
        for(Node child=root.getFirstChild();child!=null;child=child.getNextSibling()) {
            if(child instanceof Element) projection.node((Element)child,0);
            else require(child.getNodeType()==Node.TEXT_NODE && child.getTextContent().trim().isEmpty());
        }
        require(projection.codes==1 && projection.names==1 && projection.periods==1
            && projection.prices==1 && projection.orderBooks==1);
        return projection.canonical.toString();
    }

    /** One before/image/after transaction. No automatic retry or replay. */
    public static <T> T capture(Port<T> port,String symbol,String name) throws Exception {
        String before=project(port.observe(),symbol,name);
        T image=port.capture();
        boolean accepted=false;
        try {
            require(image!=null);
            String after=project(port.observe(),symbol,name);
            require(before.equals(after));
            accepted=true;return image;
        } finally { if(!accepted && image!=null)port.discard(image); }
    }
}
