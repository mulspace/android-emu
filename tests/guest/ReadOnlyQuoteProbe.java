import club.lang.resources.ReadOnlyQuote;
import java.nio.file.Files;
import java.nio.file.Paths;

public class ReadOnlyQuoteProbe {
    static final String P="com.guotai.dazhihui", SURFACE=P+":720:1560:0";
    static int scenarios;
    static void check(boolean ok){if(!ok)throw new AssertionError();}
    static String n(String id,String text,String selected){
        return "<node class=\"android.widget.TextView\" package=\""+P+"\" resource-id=\""+P+":id/"+id
            +"\" text=\""+text+"\" content-desc=\"\" password=\"false\" selected=\""+selected
            +"\" clickable=\"false\" bounds=\"[0,0][100,100]\"/>";
    }
    static String clock(String time){return "<node class=\"android.widget.TextView\" package=\"com.android.systemui\""
        +" resource-id=\"com.android.systemui:id/clock\" text=\""+time+"\" content-desc=\""+time
        +" PM\" password=\"false\" clickable=\"false\"/>";}
    static String base(){return "<hierarchy rotation=\"0\">"+n("stock_name","招商证券","false")
        +n("stock_code","600999","false")+n("minutes","分时","true")
        +n("five_level","五档","true")+n("current_price","15.39","false")
        +n("gain","-0.29  [-1.85%]","false")+n("summary_value","46.33万","false")
        +n("detail_value","1338亿","false")+n("bottom_index_name","上证","false")
        +n("bottom_index_price","3649.13","false")+n("bottom_index_chg","-0.88%","false")
        +n("buy","买","false")+clock("14:59")+"</hierarchy>";}
    static class Port implements ReadOnlyQuote.Port<Object> {
        ReadOnlyQuote.State before,after; int observes,captures,discards; Object pixels=new Object();
        boolean throwAfter=false;
        Port(String a,String b){before=new ReadOnlyQuote.State(SURFACE,a,false);after=new ReadOnlyQuote.State(SURFACE,b,false);}
        public ReadOnlyQuote.State observe() throws Exception {
            if(++observes==2 && throwAfter)throw new Exception("cancelled");
            return observes==1?before:after;
        }
        public Object capture(){captures++;return pixels;}
        public void discard(Object image){check(image==pixels);discards++;}
    }
    static void accept(String a,String b)throws Exception {
        Port port=new Port(a,b);check(ReadOnlyQuote.capture(port,"600999","招商证券")==port.pixels);
        check(port.observes==2 && port.captures==1 && port.discards==0);scenarios++;
    }
    static void refuse(String a,String b,boolean pre)throws Exception {
        Port port=new Port(a,b);
        try{ReadOnlyQuote.capture(port,"600999","招商证券");throw new AssertionError();}catch(Exception expected){}
        check(port.captures==(pre?0:1) && port.discards==(pre?0:1));scenarios++;
    }
    public static void main(String[] args)throws Exception {
        String a=base();accept(a,a);
        String updated=a.replace("15.39","15.42").replace("-0.29  [-1.85%]","-0.26  [-1.66%]")
            .replace("46.33万","46.40万").replace("1338亿","1340亿")
            .replace("上证","深证").replace("3649.13","11680.22").replace("-0.88%","+0.26%")
            .replace("14:59","15:00");accept(a,updated);
        for(String changed:new String[]{a.replace("600999","600150"),a.replace("招商证券","中国船舶"),
                a.replace("text=\"分时\"","text=\"日K\""),a.replace("selected=\"true\"","selected=\"false\""),
                a.replace("[0,0][100,100]","[0,0][101,100]"),a.replace("text=\"买\"","text=\"确认买入\""),
                a.replace("clickable=\"false\"","clickable=\"true\""),a.replace("1338亿","请登录"),
                a.replace("上证","未知指数"),
                a.replace("password=\"false\"","password=\"true\""),
                a.replace("</hierarchy>",n("stock_code","600999","false")+"</hierarchy>"),
                a.replace("</hierarchy>",n("account","123456","false")+"</hierarchy>"),
                a.replace("com.android.systemui","other.overlay")})refuse(a,changed,false);
        for(String bad:new String[]{a.replace("600999","600150"),a.replace("15.39","password"),
                a.replace("android.widget.TextView","android.widget.EditText"),
                "<!DOCTYPE hierarchy [<!ENTITY e SYSTEM 'file:///etc/passwd'>]>"+a,
                a.replace("</hierarchy>",""),"<hierarchy/>"})refuse(bad,a,true);
        Port sensitive=new Port(a,a);sensitive.after=new ReadOnlyQuote.State(SURFACE,a,true);
        try{ReadOnlyQuote.capture(sensitive,"600999","招商证券");throw new AssertionError();}catch(Exception expected){}
        check(sensitive.discards==1);scenarios++;
        Port rotated=new Port(a,a);rotated.after=new ReadOnlyQuote.State(P+":1560:720:1",a,false);
        try{ReadOnlyQuote.capture(rotated,"600999","招商证券");throw new AssertionError();}catch(Exception expected){}
        check(rotated.discards==1);scenarios++;
        Port cancelled=new Port(a,a);cancelled.throwAfter=true;
        try{ReadOnlyQuote.capture(cancelled,"600999","招商证券");throw new AssertionError();}catch(Exception expected){}
        check(cancelled.discards==1 && cancelled.captures==1);scenarios++;
        Port empty=new Port(a,a);empty.pixels=null;
        try{ReadOnlyQuote.capture(empty,"600999","招商证券");throw new AssertionError();}catch(Exception expected){}
        check(empty.discards==0 && empty.observes==1);scenarios++;
        if(args.length==1) {
            // Optional private replay: only counts are printed; no actual quote
            // values are committed to the fixture or modified on the device.
            String real=new String(Files.readAllBytes(Paths.get(args[0])),"UTF-8");
            accept(real,real);
        }
        System.out.println("Read-only quote: "+scenarios+" scenarios passed");
    }
}
