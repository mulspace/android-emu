import club.lang.resources.StableChildRecovery;
import java.util.*;

public final class StableChildRecoveryProbe {
    static class Fake implements StableChildRecovery.Port<String> {
        Object before=Arrays.asList("same", 2, 11L, 12L), after=before;
        boolean refreshed=true, expired=false, failed=false;
        int checks=0, refreshes=0, reads=0, states=0;
        String result="child";
        public void check() { if(++checks==2 && expired)throw new IllegalStateException(); }
        public Object state() { return states++==0 ? before : after; }
        public boolean refresh(){++refreshes;if(failed)throw new IllegalStateException();return refreshed;}
        public String read(){++reads;return result;}
    }
    static void require(boolean value){if(!value)throw new AssertionError();}
    static void rejected(Fake p){require(StableChildRecovery.recover(p)==null);require(p.reads==0);require(p.refreshes<=1);}
    public static void main(String[] args){
        Fake same=new Fake();same.after=new ArrayList<>((List<?>)same.before);
        require("child".equals(StableChildRecovery.recover(same)));require(same.reads==1 && same.refreshes==1 && same.checks==2);
        Fake gone=new Fake();gone.refreshed=false;rejected(gone);
        Fake attr=new Fake();attr.after=Arrays.asList("changed",2,11L,12L);rejected(attr);
        Fake ids=new Fake();ids.after=Arrays.asList("same",2,11L,99L);rejected(ids);
        Fake order=new Fake();order.after=Arrays.asList("same",2,12L,11L);rejected(order);
        Fake count=new Fake();count.after=Arrays.asList("same",1,11L);rejected(count);
        Fake missingState=new Fake();missingState.before=null;rejected(missingState);require(missingState.refreshes==0);
        Fake missingAfter=new Fake();missingAfter.after=null;rejected(missingAfter);
        Fake stillMissing=new Fake();stillMissing.result=null;require(StableChildRecovery.recover(stillMissing)==null);require(stillMissing.reads==1);
        for(boolean expiration:new boolean[]{true,false}){
            Fake failed=new Fake();failed.expired=expiration;failed.failed=!expiration;
            try{StableChildRecovery.recover(failed);throw new AssertionError();}catch(IllegalStateException expected){}
            require(failed.reads==0 && failed.refreshes==1);
        }
        System.out.println("11 stable-child recovery scenarios passed");
    }
}
